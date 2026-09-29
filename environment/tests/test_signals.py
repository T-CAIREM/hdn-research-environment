from datetime import datetime, timedelta
from unittest import skipIf
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from environment.signals import (
    ActiveProject,
    DataAccessRequest,
    Event,
    Training,
    User,
)

Author = apps.get_model("project", "Author")
CoreProject = apps.get_model("project", "CoreProject")
ProjectType = apps.get_model("project", "ProjectType")
PublishedProject = apps.get_model("project", "PublishedProject")
TrainingType = apps.get_model("user", "TrainingType")


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class UserSignalsTestCase(TestCase):
    def test_memoizes_original_credentialing_on_init(self):
        new_user = User()
        self.assertEqual(new_user._original_is_credentialed, new_user.is_credentialed)

    @patch("environment.signals.stop_environments_with_expired_access")
    def test_schedules_task_on_save_if_credentialing_was_revoked(
        self, mock_stop_environments_with_expired_access
    ):
        new_user = User(is_credentialed=True)
        new_user.is_credentialed = False
        new_user.save()
        mock_stop_environments_with_expired_access.assert_called()


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class TrainingSignalsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.training_type = TrainingType.objects.create(
            name="Test training", valid_duration=timedelta(days=365)
        )

    def test_memoizes_original_validity_on_init(self):
        new_user = User()
        new_user.save()
        new_training = Training(user=new_user, training_type=self.training_type)
        self.assertEqual(new_training._original_is_valid, new_training.is_valid())

    @patch("environment.signals.stop_environments_with_expired_access")
    def test_schedules_task_on_save_if_training_was_accepted(
        self, mock_stop_environments_with_expired_access
    ):
        new_user = User()
        new_user.save()
        new_training = Training(
            user=new_user,
            process_datetime=timezone.now(),
            training_type=self.training_type,
        )
        new_training._original_is_valid = False
        new_training.is_valid = lambda: True
        new_training.save()
        mock_stop_environments_with_expired_access.assert_called()


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class DataAccessRequestSignalsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        resource_type = ProjectType.objects.create(
            id=99, name="Test dataset", description="Test dataset"
        )
        cls.project = PublishedProject.objects.create(
            core_project=CoreProject.objects.create(),
            resource_type=resource_type,
            title="Test dataset",
            slug="test-dataset",
            submission_slug="test-dataset-submission",
            version="1.0",
        )

    def test_memoizes_original_is_accepted_on_init(self):
        new_access_request = DataAccessRequest()
        self.assertEqual(
            new_access_request._original_is_accepted, new_access_request.is_accepted()
        )

    def test_memoizes_original_is_revoked_on_init(self):
        new_access_request = DataAccessRequest()
        self.assertEqual(
            new_access_request._original_is_revoked, new_access_request.is_revoked()
        )

    @patch("environment.signals.stop_environments_with_expired_access")
    def test_does_not_schedule_task_on_save_if_access_duration_was_not_specified(
        self, mock_stop_environments_with_expired_access
    ):
        requester = User()
        requester.save()
        new_data_access_request = DataAccessRequest(
            requester=requester, project=self.project
        )
        new_data_access_request._original_is_accepted = False
        new_data_access_request.is_accepted = lambda: True
        new_data_access_request.save()
        mock_stop_environments_with_expired_access.assert_not_called()

    @patch("environment.signals.stop_environments_with_expired_access")
    def test_schedules_task_on_save_if_request_with_duration_was_accepted(
        self, mock_stop_environments_with_expired_access
    ):
        requester = User()
        requester.save()
        new_data_access_request = DataAccessRequest(
            requester=requester, project=self.project, duration=timedelta(days=10)
        )
        new_data_access_request._original_is_accepted = False
        new_data_access_request.is_accepted = lambda: True
        new_data_access_request.save()
        mock_stop_environments_with_expired_access.assert_called()

    @patch("environment.signals.stop_environments_with_expired_access")
    def test_schedules_task_on_save_if_access_was_revoked(
        self, mock_stop_environments_with_expired_access
    ):
        requester = User()
        requester.save()
        new_data_access_request = DataAccessRequest(
            requester=requester, project=self.project
        )
        new_data_access_request._original_is_revoked = False
        new_data_access_request.is_revoked = lambda: True
        new_data_access_request.save()
        mock_stop_environments_with_expired_access.assert_called()


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class EventSignalsTestCase(TestCase):
    def test_memoize_original_event_end_time(self):
        new_event = Event()
        self.assertEqual(new_event._original_end_date, new_event.end_date)

    @patch(
        "environment.signals.stop_event_participants_environments_with_expired_access"
    )
    def test_schedule_stop_environments_if_event_finished(
        self, mock_stop_event_participants_environments_with_expired_access
    ):
        host = User()
        host.save()

        event = Event(host_id=host.id, end_date=datetime(year=2000, month=12, day=12))
        event.save()

        mock_stop_event_participants_environments_with_expired_access.assert_called_with(
            event.id, schedule=event.end_date
        )


class DraftSignalFixtureMixin:
    UNSUBMITTED = 0
    NEEDS_ASSIGNMENT = 10

    def setUp(self):
        self.user = User.objects.create_user("draft-author", "author@example.com", "pw")
        self.resource_type, _created = ProjectType.objects.get_or_create(
            id=99, defaults={"name": "Test type", "description": "Test type"}
        )

    def _create_draft(self, is_submitting=True):
        project = ActiveProject.objects.create(
            core_project=CoreProject.objects.create(),
            resource_type=self.resource_type,
            title="owned-draft",
            slug="owned-draft",
            submission_status=self.UNSUBMITTED,
        )
        Author.objects.create(
            project=project,
            user=self.user,
            display_order=1,
            is_submitting=is_submitting,
        )
        return project


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
@override_settings(CLOUD_RESEARCH_ENVIRONMENTS_ENABLE_DRAFT_WORKBENCHES=True)
class ActiveProjectSignalsTestCase(DraftSignalFixtureMixin, TestCase):
    """A draft leaving the author-editable set must stop its writable workbenches."""

    @patch("environment.signals.stop_environments_with_expired_access")
    def test_schedules_task_when_draft_is_submitted(self, mock_stop):
        project = self._create_draft()
        mock_stop.reset_mock()

        project.submission_status = self.NEEDS_ASSIGNMENT
        project.save()

        mock_stop.assert_called_once_with(self.user.id)

    @patch("environment.signals.stop_environments_with_expired_access")
    def test_does_not_schedule_while_the_draft_stays_editable(self, mock_stop):
        project = self._create_draft()
        mock_stop.reset_mock()

        project.title = "renamed draft"
        project.save()

        mock_stop.assert_not_called()

    @patch("environment.signals.stop_environments_with_expired_access")
    def test_schedules_task_when_draft_is_deleted(self, mock_stop):
        project = self._create_draft()
        mock_stop.reset_mock()

        # Publication deletes the ActiveProject row; the Author rows cascade,
        # so the submitting authors are read in pre_delete.
        project.delete()

        mock_stop.assert_called_once_with(self.user.id)

    @patch("environment.signals.stop_environments_with_expired_access")
    def test_only_submitting_authors_are_scheduled(self, mock_stop):
        project = self._create_draft(is_submitting=False)
        mock_stop.reset_mock()

        project.submission_status = self.NEEDS_ASSIGNMENT
        project.save()
        project.delete()

        mock_stop.assert_not_called()


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
@override_settings(CLOUD_RESEARCH_ENVIRONMENTS_ENABLE_DRAFT_WORKBENCHES=False)
class ActiveProjectSignalsDisabledTestCase(DraftSignalFixtureMixin, TestCase):
    """With draft workbenches off, draft state changes queue no reaper work."""

    @patch("environment.signals.stop_environments_with_expired_access")
    def test_submitting_a_draft_queues_nothing(self, mock_stop):
        project = self._create_draft()

        project.submission_status = self.NEEDS_ASSIGNMENT
        project.save()

        mock_stop.assert_not_called()

    @patch("environment.signals.stop_environments_with_expired_access")
    def test_deleting_a_draft_queues_nothing(self, mock_stop):
        project = self._create_draft()

        project.delete()

        mock_stop.assert_not_called()
