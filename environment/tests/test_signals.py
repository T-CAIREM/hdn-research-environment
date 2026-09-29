import json
from datetime import datetime, timedelta
from unittest import skipIf
from unittest.mock import patch

import requests
from background_task.models import CompletedTask, Task
from background_task.tasks import tasks as background_tasks
from django.apps import apps
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from environment.models import BillingAccountSharingInvite, CloudIdentity
from environment.signals import (
    ActiveProject,
    DataAccessRequest,
    Event,
    EventApplication,
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


def _user(username: str, with_cloud_identity: bool = True):
    user = User.objects.create_user(
        email=f"{username}@example.com", password="pw", username=username
    )
    if with_cloud_identity:
        CloudIdentity.objects.create(
            user=user, gcp_user_id=username, email=f"{username}@example.com"
        )
    return user


def _api_response(status_code: int, body: dict) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(body).encode()
    response.headers["Content-Type"] = "application/json"
    return response


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
@override_settings(BACKGROUND_TASK_RUN_ASYNC=False)
class EventApprovalBillingShareTestCase(TestCase):
    """#190: approving an event application shares the event's billing account
    through a durable, retried invite, never inline."""

    BILLING_ACCOUNT_ID = "012345-6789AB-CDEF01"
    SHARE_TASK = "environment.tasks.give_user_permission_to_access_billing_account"

    def setUp(self):
        self.host = _user("host")
        self.event = Event.objects.create(
            title="Workshop",
            host=self.host,
            end_date=timezone.now().date() + timedelta(days=7),
            gcp_billing_id=self.BILLING_ACCOUNT_ID,
        )
        # Scheduling the event's own reaper task is not under test.
        Task.objects.all().delete()

    def _participant(self, with_cloud_identity=True):
        return _user("participant", with_cloud_identity)

    def _approve(self, user):
        application = EventApplication.objects.create(user=user, event=self.event)
        with self.captureOnCommitCallbacks() as callbacks:
            application.accept(comment_to_applicant="")
        return application, callbacks

    def _invites(self, user):
        return BillingAccountSharingInvite.objects.filter(
            user=user, billing_account_id=self.BILLING_ACCOUNT_ID
        )

    def _share_tasks(self):
        return Task.objects.filter(task_name=self.SHARE_TASK)

    def _run_share_task(self):
        # Run the queued task the way the task runner does, ignoring its backoff.
        self._share_tasks().update(run_at=timezone.now() - timedelta(seconds=1))
        self.assertTrue(background_tasks.run_next_task())

    @patch("environment.services.api.share_billing_account")
    def test_queues_the_share_only_after_the_approval_commits(self, mock_share):
        user = self._participant()

        _application, callbacks = self._approve(user)

        # Nothing is shared inline, and nothing is queued before the commit.
        mock_share.assert_not_called()
        self.assertFalse(self._share_tasks().exists())
        invite = self._invites(user).get()
        self.assertEqual(invite.owner, self.host)
        self.assertFalse(invite.is_consumed)

        for callback in callbacks:
            callback()

        self.assertEqual(
            [task.params() for task in self._share_tasks()],
            [
                (
                    [
                        invite.id,
                        "host@example.com",
                        "participant@example.com",
                        self.BILLING_ACCOUNT_ID,
                    ],
                    {},
                )
            ],
        )

    @patch("environment.services.api.share_billing_account")
    def test_an_api_5xx_is_retried_until_the_share_succeeds(self, mock_share):
        user = self._participant()
        _application, callbacks = self._approve(user)
        for callback in callbacks:
            callback()
        invite = self._invites(user).get()

        mock_share.return_value = _api_response(503, {"error": "Try again"})
        self._run_share_task()

        task = self._share_tasks().get()
        self.assertEqual(task.attempts, 1)
        self.assertIn("BillingSharingFailed", task.last_error)
        invite.refresh_from_db()
        self.assertFalse(invite.is_consumed)

        mock_share.return_value = _api_response(200, {})
        self._run_share_task()

        self.assertFalse(self._share_tasks().exists())
        self.assertTrue(
            CompletedTask.objects.filter(task_name=self.SHARE_TASK).exists()
        )
        invite.refresh_from_db()
        self.assertTrue(invite.is_consumed)
        self.assertEqual(mock_share.call_count, 2)
        mock_share.assert_called_with(
            owner_email="host@example.com",
            user_email="participant@example.com",
            billing_account_id=self.BILLING_ACCOUNT_ID,
        )

    @patch("environment.services.api.share_billing_account")
    def test_an_api_timeout_is_retried(self, mock_share):
        user = self._participant()
        _application, callbacks = self._approve(user)
        for callback in callbacks:
            callback()
        mock_share.side_effect = requests.exceptions.ReadTimeout("timed out")

        self._run_share_task()

        task = self._share_tasks().get()
        self.assertEqual(task.attempts, 1)
        self.assertFalse(self._invites(user).get().is_consumed)

    def test_reapproval_reuses_the_invite_and_does_not_duplicate_the_task(self):
        user = self._participant()
        application, callbacks = self._approve(user)
        for callback in callbacks:
            callback()

        application.reject(comment_to_applicant="")
        application = EventApplication.objects.get(pk=application.pk)
        with self.captureOnCommitCallbacks(execute=True):
            application._apply_decision(
                EventApplication.EventApplicationStatus.APPROVED, ""
            )

        self.assertEqual(self._invites(user).count(), 1)
        # The first task is still pending, so an identical one is not queued.
        self.assertEqual(self._share_tasks().count(), 1)

    def test_reuses_an_invite_the_user_already_holds(self):
        user = self._participant()
        existing = BillingAccountSharingInvite.objects.create(
            owner=self.host,
            user=user,
            user_contact_email=user.email,
            billing_account_id=self.BILLING_ACCOUNT_ID,
            is_consumed=True,
        )

        _application, callbacks = self._approve(user)
        for callback in callbacks:
            callback()

        self.assertEqual(list(self._invites(user)), [existing])
        # Sharing again is idempotent and repairs a grant that was undone.
        self.assertEqual(self._share_tasks().get().params()[0][0], existing.id)

    def test_a_revoked_invite_is_not_reused(self):
        user = self._participant()
        revoked = BillingAccountSharingInvite.objects.create(
            owner=self.host,
            user=user,
            user_contact_email=user.email,
            billing_account_id=self.BILLING_ACCOUNT_ID,
            is_revoked=True,
        )

        self._approve(user)

        self.assertEqual(self._invites(user).exclude(pk=revoked.pk).count(), 1)

    def test_without_a_cloud_identity_the_share_waits_for_one(self):
        user = self._participant(with_cloud_identity=False)

        _application, callbacks = self._approve(user)
        for callback in callbacks:
            callback()

        invite = self._invites(user).get()
        self.assertEqual(invite.owner, self.host)
        self.assertEqual(invite.user_contact_email, user.email)
        self.assertFalse(self._share_tasks().exists())

        # Unchanged path: creating the identity queues the outstanding share.
        with self.captureOnCommitCallbacks(execute=True):
            CloudIdentity.objects.create(
                user=user, gcp_user_id=user.username, email="participant@example.com"
            )

        self.assertEqual(self._share_tasks().get().params()[0][0], invite.id)

    def test_a_host_without_a_cloud_identity_is_logged_not_raised(self):
        self.host.cloud_identity.delete()
        self.host = User.objects.get(pk=self.host.pk)
        self.event.host = self.host
        self.event.save()
        user = self._participant()

        with self.assertLogs("environment.signals", level="ERROR"):
            self._approve(user)

        self.assertFalse(self._invites(user).exists())

    def test_nothing_happens_for_an_event_without_a_billing_account(self):
        self.event.gcp_billing_id = None
        self.event.save()
        user = self._participant()

        self._approve(user)

        self.assertFalse(self._invites(user).exists())
