from datetime import timedelta
from unittest import skipIf
from unittest.mock import Mock, call, patch

from django.conf import settings
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from environment.entities import (
    EnvironmentStatus,
    EnvironmentType,
    Region,
    ResearchEnvironment,
)
from environment.mailers import send_environment_access_expired
from environment.tasks import (
    stop_environments_with_expired_access,
    terminate_environments_if_access_still_expired,
)
from environment.tests.helpers import create_user_with_cloud_identity


def _environment(
    gcp_identifier: str,
    dataset_identifier: str = "demoproject100",
    status: EnvironmentStatus = EnvironmentStatus.RUNNING,
) -> ResearchEnvironment:
    return ResearchEnvironment(
        gcp_identifier=gcp_identifier,
        dataset_identifier=dataset_identifier,
        url=None,
        workspace_name="proj-123",
        status=status,
        cpu=2,
        memory=8,
        region=Region.US_CENTRAL,
        type=EnvironmentType.JUPYTER,
        project=None,
        machine_type="n1-standard-2",
        disk_size=100,
        gpu_accelerator_type=None,
        service_account_name=None,
        workbench_owner_username=None,
        rstudio_ssl_certificate_expiration_date=None,
    )


def _project(model_name: str, label: str) -> Mock:
    project = Mock()
    project._meta.model_name = model_name
    project.__str__ = Mock(return_value=label)
    return project


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class StopEnvironmentsWithExpiredAccessTestCase(TestCase):
    """The reaper's stop leg: it must call the services with their real signatures."""

    def setUp(self):
        self.user = create_user_with_cloud_identity()

    def _run(self, pairs):
        with patch(
            "environment.tasks.get_environment_project_pairs_with_expired_access",
            return_value=pairs,
        ), patch("environment.tasks.stop_running_environment") as mock_stop, patch(
            "environment.tasks.send_environment_access_expired"
        ) as mock_mail, patch(
            "environment.tasks.terminate_environments_if_access_still_expired"
        ) as mock_terminate:
            stop_environments_with_expired_access.now(self.user.id)
        return mock_stop, mock_mail, mock_terminate

    def _assert_stopped(self, mock_stop, gcp_identifier):
        mock_stop.assert_called_once_with(
            workbench_type="jupyter",
            workbench_resource_id=gcp_identifier,
            user=self.user,
            workspace_project_id="proj-123",
        )

    def test_stops_a_published_environment(self):
        environment = _environment("wb-published")
        project = _project("publishedproject", "Demo Project 1.0.0")

        mock_stop, mock_mail, mock_terminate = self._run([(environment, project)])

        self._assert_stopped(mock_stop, "wb-published")
        mock_mail.assert_called_once_with(self.user, (project,))
        self.assertEqual(
            mock_terminate.call_args.args, (self.user.id, ["wb-published"])
        )

    def test_stops_a_draft_environment(self):
        environment = _environment("wb-draft", dataset_identifier="a" + "0" * 32)
        project = _project("activeproject", "Owned draft")

        mock_stop, mock_mail, mock_terminate = self._run([(environment, project)])

        self._assert_stopped(mock_stop, "wb-draft")
        mock_mail.assert_called_once_with(self.user, (project,))
        self.assertEqual(mock_terminate.call_args.args, (self.user.id, ["wb-draft"]))

    def test_stops_an_environment_whose_draft_vanished(self):
        # The draft was deleted or published: the pair carries project=None.
        environment = _environment("wb-gone", dataset_identifier="a" + "1" * 32)

        mock_stop, mock_mail, mock_terminate = self._run([(environment, None)])

        self._assert_stopped(mock_stop, "wb-gone")
        mock_mail.assert_called_once_with(self.user, (None,))
        self.assertEqual(mock_terminate.call_args.args, (self.user.id, ["wb-gone"]))

    def test_schedules_termination_in_fourteen_days(self):
        environment = _environment("wb-published")
        before = timezone.now() + timedelta(days=14)

        _mock_stop, _mock_mail, mock_terminate = self._run([(environment, Mock())])

        schedule = mock_terminate.call_args.kwargs["schedule"]
        self.assertGreaterEqual(schedule, before)
        self.assertLess(schedule, before + timedelta(minutes=5))

    def test_does_not_stop_an_environment_that_is_not_running(self):
        environment = _environment("wb-stopped", status=EnvironmentStatus.STOPPED)

        mock_stop, mock_mail, mock_terminate = self._run([(environment, Mock())])

        mock_stop.assert_not_called()
        # It is still mailed about and still queued for termination.
        mock_mail.assert_called_once()
        self.assertEqual(mock_terminate.call_args.args, (self.user.id, ["wb-stopped"]))

    def test_does_nothing_without_expired_pairs(self):
        mock_stop, mock_mail, mock_terminate = self._run([])

        mock_stop.assert_not_called()
        mock_mail.assert_not_called()
        mock_terminate.assert_not_called()


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class TerminateEnvironmentsIfAccessStillExpiredTestCase(TestCase):
    """The reaper's destroy leg, 14 days later."""

    def setUp(self):
        self.user = create_user_with_cloud_identity()

    def _run(self, pairs, previously_stopped):
        with patch(
            "environment.tasks.get_environment_project_pairs_with_expired_access",
            return_value=pairs,
        ), patch("environment.tasks.delete_environment") as mock_delete:
            terminate_environments_if_access_still_expired.now(
                self.user.id, previously_stopped
            )
        return mock_delete

    def _expected_call(self, gcp_identifier):
        return call(
            user=self.user,
            workspace_project_id="proj-123",
            workbench_type="jupyter",
            workbench_resource_id=gcp_identifier,
        )

    def test_deletes_a_published_environment(self):
        environment = _environment("wb-published")
        project = _project("publishedproject", "Demo Project 1.0.0")

        mock_delete = self._run([(environment, project)], ["wb-published"])

        self.assertEqual(
            mock_delete.call_args_list, [self._expected_call("wb-published")]
        )

    def test_deletes_a_draft_environment(self):
        environment = _environment("wb-draft", dataset_identifier="a" + "0" * 32)
        project = _project("activeproject", "Owned draft")

        mock_delete = self._run([(environment, project)], ["wb-draft"])

        self.assertEqual(mock_delete.call_args_list, [self._expected_call("wb-draft")])

    def test_deletes_an_environment_whose_draft_vanished(self):
        # project=None must not be dereferenced: the old code called
        # project.project_file_root() here.
        environment = _environment("wb-gone", dataset_identifier="a" + "1" * 32)

        mock_delete = self._run([(environment, None)], ["wb-gone"])

        self.assertEqual(mock_delete.call_args_list, [self._expected_call("wb-gone")])

    def test_skips_environments_that_were_not_previously_stopped(self):
        environment = _environment("wb-new")

        mock_delete = self._run([(environment, Mock())], ["wb-published"])

        mock_delete.assert_not_called()

    def test_skips_environments_whose_access_came_back(self):
        mock_delete = self._run([], ["wb-published"])

        mock_delete.assert_not_called()


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class ExpiredAccessMailTestCase(TestCase):
    """The mail body has to survive a vanished draft (project=None)."""

    def setUp(self):
        self.user = create_user_with_cloud_identity()

    def test_renders_a_generic_line_for_a_vanished_draft(self):
        project = _project("publishedproject", "Demo Project 1.0.0")

        send_environment_access_expired(self.user, (project, None))

        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("Demo Project 1.0.0", body)
        self.assertIn("A draft project that is no longer available", body)
        self.assertNotIn("None", body)
