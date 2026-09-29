from datetime import timedelta
from unittest import skipIf
from unittest.mock import Mock, call, patch

from background_task.models import Task
from django.apps import apps
from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from environment.deserializers import _project_data_group
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
from environment.tests.helpers import (
    create_user_with_cloud_identity,
    create_user_without_cloud_identity,
)
from project.models import AccessPolicy

CoreProject = apps.get_model("project", "CoreProject")
ProjectType = apps.get_model("project", "ProjectType")
PublishedProject = apps.get_model("project", "PublishedProject")

ENFORCE = override_settings(
    CLOUD_RESEARCH_ENVIRONMENTS_EXPIRED_ACCESS_ENFORCEMENT="enforce"
)
DRY_RUN = override_settings(
    CLOUD_RESEARCH_ENVIRONMENTS_EXPIRED_ACCESS_ENFORCEMENT="dry_run"
)
OFF = override_settings(CLOUD_RESEARCH_ENVIRONMENTS_EXPIRED_ACCESS_ENFORCEMENT="off")


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
@ENFORCE
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
@ENFORCE
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


def _published_project(slug: str, access_policy: int):
    resource_type, _created = ProjectType.objects.get_or_create(
        id=99, defaults={"name": "Test type", "description": "Test type"}
    )
    return PublishedProject.objects.create(
        core_project=CoreProject.objects.create(),
        resource_type=resource_type,
        title=f"Dataset {slug}",
        slug=slug,
        submission_slug=slug,
        version="1.0",
        access_policy=access_policy,
    )


def _workbench_payload(gcp_identifier: str, dataset_identifier: str) -> dict:
    return {
        "type": "Workbench",
        "gcp_identifier": gcp_identifier,
        "dataset_identifier": dataset_identifier,
        "url": None,
        "status": "running",
        "cpu": 2,
        "memory": 8,
        "region": "us-central1",
        "workbench_type": "jupyter",
        "machine_type": "n1-standard-2",
        "disk_size": 100,
        "gpu_accelerator_type": None,
        "service_account_name": None,
        "workbench_owner_username": None,
        "rstudio_ssl_certificate_expiration_date": None,
        "service_errors": [],
    }


def _json_response(body) -> Mock:
    response = Mock(ok=True, status_code=200)
    response.json.return_value = body
    return response


class ExpiredAccessFixtureMixin:
    """A workspaces response with every shape #187 tripped over, backed by
    real PublishedProject rows (no mocked access method)."""

    TERMINATE_TASK = "environment.tasks.terminate_environments_if_access_still_expired"

    def setUp(self):
        self.user = create_user_with_cloud_identity()
        self.open_project = _published_project("open-data", AccessPolicy.OPEN)
        # The user is not credentialed, so a credentialed project is not accessible.
        self.expired_project = _published_project(
            "credentialed-data", AccessPolicy.CREDENTIALED
        )
        patcher = patch(
            "environment.services.api.get_workspace_list",
            return_value=_json_response(self._workspaces()),
        )
        self.mock_get_workspace_list = patcher.start()
        self.addCleanup(patcher.stop)

    def _workspaces(self):
        return [
            # A workspace that is still being created.
            {
                "type": "EntityScaffolding",
                "gcp_project_id": "proj-new",
                "status": "creating",
            },
            {
                "type": "Workspace",
                "gcp_project_id": "proj-123",
                "status": "created",
                "is_owner": True,
                "billing_info": None,
                "service_errors": [],
                "workbenches": [
                    # A workbench that is still being created (no is_active).
                    {
                        "type": "EntityScaffolding",
                        "gcp_project_id": "proj-123",
                        "status": "creating",
                    },
                    _workbench_payload(
                        "wb-expired", _project_data_group(self.expired_project)
                    ),
                    _workbench_payload(
                        "wb-open", _project_data_group(self.open_project)
                    ),
                ],
            },
        ]

    def _queued_terminations(self):
        return [
            task.params() for task in Task.objects.filter(task_name=self.TERMINATE_TASK)
        ]


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
@ENFORCE
class ExpiredAccessEnforceRegressionTestCase(ExpiredAccessFixtureMixin, TestCase):
    """#187: the stop task must run end to end, not crash, and act only on
    the workbench whose published-project access has expired."""

    @patch("environment.services.api.stop_workbench")
    def test_stops_mails_and_queues_termination_for_the_expired_workbench(
        self, mock_stop_workbench
    ):
        mock_stop_workbench.return_value = _json_response({"workflow_id": "wf-stop"})

        stop_environments_with_expired_access.now(self.user.id)

        mock_stop_workbench.assert_called_once_with(
            workbench_type="jupyter",
            workbench_resource_id="wb-expired",
            user_email=self.user.cloud_identity.email,
            workspace_project_id="proj-123",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.expired_project.title, mail.outbox[0].body)
        self.assertNotIn(self.open_project.title, mail.outbox[0].body)
        self.assertEqual(
            self._queued_terminations(), [([self.user.id, ["wb-expired"]], {})]
        )

    @patch("environment.services.api.delete_workbench")
    def test_terminates_the_workbench_still_expired_14_days_later(
        self, mock_delete_workbench
    ):
        mock_delete_workbench.return_value = _json_response(
            {"workflow_id": "wf-delete"}
        )

        terminate_environments_if_access_still_expired.now(
            self.user.id, ["wb-expired", "wb-open"]
        )

        mock_delete_workbench.assert_called_once_with(
            workbench_type="jupyter",
            user_email=self.user.cloud_identity.email,
            workspace_project_id="proj-123",
            workbench_resource_id="wb-expired",
        )


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class ExpiredAccessDryRunTestCase(ExpiredAccessFixtureMixin, TestCase):
    """dry_run is the default: a full inventory in the log, and no side effects."""

    def test_dry_run_is_the_default(self):
        with self.settings():
            name = "CLOUD_RESEARCH_ENVIRONMENTS_EXPIRED_ACCESS_ENFORCEMENT"
            if hasattr(settings, name):
                delattr(settings, name)
            self._assert_stop_is_a_dry_run()

    @DRY_RUN
    def test_stop_task_only_logs(self):
        self._assert_stop_is_a_dry_run()

    @patch("environment.services.api.stop_workbench")
    def _assert_stop_is_a_dry_run(self, mock_stop_workbench):
        with self.assertLogs("environment.tasks", level="INFO") as logs:
            stop_environments_with_expired_access.now(self.user.id)

        mock_stop_workbench.assert_not_called()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(self._queued_terminations(), [])
        output = "\n".join(logs.output)
        self.assertIn('"workbench": "wb-expired"', output)
        self.assertIn('"action": "stop"', output)
        self.assertIn(
            f'"project": "publishedproject:{self.expired_project.pk}"', output
        )
        self.assertNotIn("wb-open", output)

    @DRY_RUN
    @patch("environment.services.api.delete_workbench")
    def test_terminate_task_only_logs(self, mock_delete_workbench):
        with self.assertLogs("environment.tasks", level="INFO") as logs:
            terminate_environments_if_access_still_expired.now(
                self.user.id, ["wb-expired"]
            )

        mock_delete_workbench.assert_not_called()
        output = "\n".join(logs.output)
        self.assertIn('"action": "delete"', output)
        self.assertIn('"workbench": "wb-expired"', output)

    @override_settings(
        CLOUD_RESEARCH_ENVIRONMENTS_EXPIRED_ACCESS_ENFORCEMENT="enforced"
    )
    @patch("environment.services.api.stop_workbench")
    def test_an_unrecognised_mode_is_a_dry_run(self, mock_stop_workbench):
        with self.assertLogs("environment.config", level="ERROR"):
            stop_environments_with_expired_access.now(self.user.id)

        mock_stop_workbench.assert_not_called()
        self.assertEqual(mail.outbox, [])


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class ExpiredAccessOffTestCase(ExpiredAccessFixtureMixin, TestCase):
    @OFF
    def test_off_does_not_consult_the_api(self):
        stop_environments_with_expired_access.now(self.user.id)
        terminate_environments_if_access_still_expired.now(self.user.id, ["wb-expired"])

        self.mock_get_workspace_list.assert_not_called()
        self.assertEqual(mail.outbox, [])


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
@ENFORCE
class ExpiredAccessWithoutCloudIdentityTestCase(TestCase):
    """A user whose access changed before they set up a cloud identity has no
    workbenches, so both tasks return early instead of crashing."""

    def setUp(self):
        self.user = create_user_without_cloud_identity()

    @patch("environment.services.api.get_workspace_list")
    def test_both_tasks_return_early(self, mock_get_workspace_list):
        with self.assertLogs("environment.tasks", level="INFO") as logs:
            stop_environments_with_expired_access.now(self.user.id)
            terminate_environments_if_access_still_expired.now(self.user.id, ["wb"])

        mock_get_workspace_list.assert_not_called()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(sum("no cloud identity" in line for line in logs.output), 2)
