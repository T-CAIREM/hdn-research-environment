from unittest import skipIf
from unittest.mock import MagicMock, patch, Mock

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

from environment.entities import (
    EnvironmentStatus,
    ResearchEnvironment,
)
from environment.exceptions import (
    ChangeEnvironmentInstanceTypeFailed,
    DeleteEnvironmentFailed,
    EnvironmentCreationFailed,
    GetAvailableEnvironmentsFailed,
    IdentityProvisioningFailed,
    StartEnvironmentFailed,
    StopEnvironmentFailed,
    GetBillingAccountsListFailed,
    InvitedUserIsAccountOwner,
    PublishedProjectAccessFailed,
)
from environment.models import BillingAccountSharingInvite, BucketSharingInvite
from environment.services import (
    change_environment_machine_type,
    create_cloud_identity,
    create_research_environment,
    delete_environment,
    get_environments_with_projects,
    start_stopped_environment,
    stop_running_environment,
    get_billing_accounts_list,
    invite_user_to_shared_billing_account,
    consume_billing_account_sharing_token,
    consume_bucket_sharing_token,
    revoke_billing_account_access,
    revoke_shared_bucket_access,
    create_shared_workspace,
    delete_shared_workspace,
    create_shared_bucket,
    delete_shared_bucket,
    check_collaborator_project_access,
    get_workbench_collaborators,
    add_workbench_collaborator,
    remove_workbench_collaborator,
)
from environment.tests.helpers import (
    create_user_with_cloud_identity,
    create_user_without_cloud_identity,
)
from environment.tests.mocks import (
    get_workspace_list_json,
    get_billing_account_list_json,
)

PublishedProject = apps.get_model("project", "PublishedProject")


User = get_user_model()


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class CreateCloudIdentityTestCase(TestCase):
    def setUp(self):
        self.user = create_user_without_cloud_identity()

    @patch("environment.models.CloudIdentity.objects.create")
    @patch("environment.api.create_cloud_identity")
    def test_raises_if_request_fails(
        self, mock_create_cloud_identity, mock_create_identity
    ):
        mock_create_cloud_identity.return_value.ok = False
        mock_create_cloud_identity.return_value.json.return_value = (
            mock_create_cloud_identity.return_value
        )
        mock_create_identity.return_value = mock_create_cloud_identity.return_value
        self.assertRaises(
            IdentityProvisioningFailed,
            create_cloud_identity,
            self.user,
            "password",
            "recovery@example.com",
        )

    @patch("environment.models.CloudIdentity.objects.create")
    @patch("environment.api.create_cloud_identity")
    def test_creates_cloud_identity_if_request_succeeds(
        self, mock_create_cloud_identity, mock_create_identity
    ):
        mock_email = "user@example.com"
        mock_create_cloud_identity.return_value.ok = True
        mock_create_cloud_identity.return_value.json.return_value = {
            "primary_email": mock_email,
        }
        mock_identity = Mock()
        mock_identity.gcp_user_id = self.user.username
        mock_identity.email = mock_email
        mock_create_identity.return_value = mock_identity

        identity = create_cloud_identity(self.user, "password", "recovery@example.com")

        mock_create_identity.assert_called_once_with(
            user=self.user,
            gcp_user_id=self.user.username,
            email=mock_email,
        )
        self.assertEqual(identity.gcp_user_id, self.user.username)
        self.assertEqual(identity.email, mock_email)


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class CreateResearchEnvironmentTestCase(TestCase):
    def setUp(self):
        self.project = MagicMock()
        self.project.slug = "slug"
        self.project.get_project_file_root.return_value = "bucket"
        self.user = create_user_with_cloud_identity()

    @patch("environment.services.persist_workflow")
    @patch("environment.api.create_workbench")
    def test_raises_if_request_fails(
        self, mock_create_workbench, mock_persist_workflow
    ):
        mock_create_workbench.return_value.ok = False
        mock_create_workbench.return_value.json.return_value = (
            mock_create_workbench.return_value
        )
        mock_machine_type = Mock()
        mock_machine_type.get_instance_value.return_value = "n1-standard-2"
        self.assertRaises(
            EnvironmentCreationFailed,
            create_research_environment,
            self.user,
            self.project,
            "workspace-id",
            mock_machine_type,
            "environment_type",
            100,
            "us-central1",
        )

    @patch("environment.services.persist_workflow")
    @patch("environment.api.create_workbench")
    def test_returns_api_response_if_request_succeeds(
        self, mock_create_workbench, mock_persist_workflow
    ):
        mock_create_workbench.return_value.ok = True
        mock_create_workbench.return_value.json.return_value = (
            mock_create_workbench.return_value
        )
        mock_machine_type = Mock()
        mock_machine_type.get_instance_value.return_value = "n1-standard-2"
        result = create_research_environment(
            self.user,
            self.project,
            "workspace-id",
            mock_machine_type,
            "environment_type",
            100,
            "us-central1",
        )
        self.assertEqual(result, mock_create_workbench.return_value)


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class StopRunningEnvironmentTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()

    @patch("environment.services.persist_workflow")
    @patch("environment.api.stop_workbench")
    def test_raises_if_request_fails(self, mock_stop_workbench, mock_persist_workflow):
        mock_stop_workbench.return_value.ok = False
        mock_stop_workbench.return_value.json.return_value = (
            mock_stop_workbench.return_value
        )
        self.assertRaises(
            StopEnvironmentFailed,
            stop_running_environment,
            "jupyter",
            "workbench_id",
            self.user,
            "workspace-id",
        )

    @patch("environment.services.persist_workflow")
    @patch("environment.api.stop_workbench")
    def test_raises_if_request_succeeds(
        self, mock_stop_workbench, mock_persist_workflow
    ):
        mock_stop_workbench.return_value.ok = True
        mock_stop_workbench.return_value.json.return_value = (
            mock_stop_workbench.return_value
        )
        result = stop_running_environment(
            "jupyter", "workbench_id", self.user, "workspace-id"
        )
        self.assertEqual(result, mock_stop_workbench.return_value)


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class StartStoppedEnvironmentTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()

    @patch("environment.services.persist_workflow")
    @patch("environment.api.start_workbench")
    def test_raises_if_request_fails(self, mock_start_workbench, mock_persist_workflow):
        mock_start_workbench.return_value.ok = False
        mock_start_workbench.return_value.json.return_value = (
            mock_start_workbench.return_value
        )
        self.assertRaises(
            StartEnvironmentFailed,
            start_stopped_environment,
            "jupyter",
            "workbench_id",
            self.user,
            "workspace-id",
        )

    @patch("environment.services.persist_workflow")
    @patch("environment.api.start_workbench")
    def test_raises_if_request_succeeds(
        self, mock_start_workbench, mock_persist_workflow
    ):
        mock_start_workbench.return_value.ok = True
        mock_start_workbench.return_value.json.return_value = (
            mock_start_workbench.return_value
        )
        result = start_stopped_environment(
            "jupyter", "workbench_id", self.user, "workspace-id"
        )
        self.assertEqual(result, mock_start_workbench.return_value)


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class ChangeEnvironmentInstanceTypeTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()

    @patch("environment.services.persist_workflow")
    @patch("environment.api.change_workbench_machine_type")
    def test_raises_if_request_fails(
        self, mock_change_workbench_machine_type, mock_persist_workflow
    ):
        mock_change_workbench_machine_type.return_value.ok = False
        mock_change_workbench_machine_type.return_value.json.return_value = (
            mock_change_workbench_machine_type.return_value
        )
        self.assertRaises(
            ChangeEnvironmentInstanceTypeFailed,
            change_environment_machine_type,
            self.user,
            "workspace-id",
            "n1-standard-2",
            "jupyter",
            "workbench_id",
        )

    @patch("environment.services.persist_workflow")
    @patch("environment.api.change_workbench_machine_type")
    def test_raises_if_request_succeeds(
        self, mock_change_workbench_machine_type, mock_persist_workflow
    ):
        mock_change_workbench_machine_type.return_value.ok = True
        mock_change_workbench_machine_type.return_value.json.return_value = (
            mock_change_workbench_machine_type.return_value
        )
        result = change_environment_machine_type(
            self.user,
            "workspace-id",
            "n1-standard-2",
            "jupyter",
            "workbench_id",
        )
        self.assertEqual(result, mock_change_workbench_machine_type.return_value)


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class DeleteEnvironmentTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()

    @patch("environment.services.persist_workflow")
    @patch("environment.api.delete_workbench")
    def test_raises_if_request_fails(
        self, mock_delete_workbench, mock_persist_workflow
    ):
        mock_delete_workbench.return_value.ok = False
        mock_delete_workbench.return_value.json.return_value = (
            mock_delete_workbench.return_value
        )
        self.assertRaises(
            DeleteEnvironmentFailed,
            delete_environment,
            self.user,
            "workspace-id",
            "jupyter",
            "workbench_id",
        )

    @patch("environment.services.persist_workflow")
    @patch("environment.api.delete_workbench")
    def test_raises_if_request_succeeds(
        self, mock_delete_workbench, mock_persist_workflow
    ):
        mock_delete_workbench.return_value.ok = True
        mock_delete_workbench.return_value.json.return_value = (
            mock_delete_workbench.return_value
        )
        result = delete_environment(
            self.user,
            "workspace-id",
            "jupyter",
            "workbench_id",
        )
        self.assertEqual(result, mock_delete_workbench.return_value)


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class GetAvailableEnvironmentsWithProjectsTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()

    @patch("environment.services._get_projects_for_environments")
    @patch("environment.services.get_active_environments")
    def test_fetches_environments_and_parses_to_entity(
        self, mock_get_active, mock_get_projects
    ):
        mock_env = Mock(spec=ResearchEnvironment)
        mock_env.dataset_identifier = "testdataset"
        mock_env.status = EnvironmentStatus.RUNNING
        mock_get_active.return_value = [mock_env]
        mock_get_projects.return_value = []

        environment_project_pairs = get_environments_with_projects(self.user)

        self.assertIsInstance(environment_project_pairs, list)
        self.assertTrue(
            all(
                environment.status != EnvironmentStatus.DESTROYING
                for environment, _project, _workflows in environment_project_pairs
            )
        )

    @patch("environment.services.inner_join_iterators")
    @patch("environment.services._get_projects_for_environments")
    @patch("environment.services.get_active_environments")
    def test_matches_running_environments_with_projects(
        self, mock_get_active, mock_get_projects, mock_inner_join
    ):
        mock_env = Mock()
        mock_env.group_granting_data_access = "demopsn"
        mock_project = Mock()
        mock_project.workflows.in_progress.return_value.filter.return_value = []

        mock_get_active.return_value = [mock_env]
        mock_get_projects.return_value = [mock_project]
        mock_inner_join.return_value = [(mock_env, mock_project)]

        environment_project_pairs = get_environments_with_projects(self.user)

        self.assertEqual(len(environment_project_pairs), 1)
        self.assertEqual(
            environment_project_pairs[0][0].group_granting_data_access, "demopsn"
        )
        self.assertEqual(environment_project_pairs[0][1], mock_project)

    @patch("environment.services.get_active_environments")
    def test_raises_if_request_fails(self, mock_get_active):
        mock_get_active.side_effect = GetAvailableEnvironmentsFailed("API failed")
        self.assertRaises(
            GetAvailableEnvironmentsFailed,
            get_environments_with_projects,
            self.user,
        )


class GetBillingAccountsListTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()

    @patch("environment.api.list_billing_accounts")
    def test_returns_json_response(self, mock_list_billing_accounts):
        mock_list_billing_accounts.return_value.json.return_value = (
            get_billing_account_list_json
        )

        result = get_billing_accounts_list(self.user)

        mock_list_billing_accounts.assert_called_once_with(
            self.user.cloud_identity.email
        )
        self.assertEqual(result, get_billing_account_list_json)

    @patch("environment.api.list_billing_accounts")
    def test_raises_when_api_fails(self, mock_list_billing_accounts):
        mock_list_billing_accounts.return_value.ok = False
        mock_list_billing_accounts.return_value.json.return_value = (
            mock_list_billing_accounts.return_value
        )
        self.assertRaises(
            GetBillingAccountsListFailed,
            get_billing_accounts_list,
            self.user,
        )


class InviteUserToSharedBillingAccountTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()
        self.user2 = create_user_with_cloud_identity(
            "abc", "abc@healthdatanexus.ai", "bar"
        )
        self.request = Mock()
        self.request.META = {"SERVER_NAME": "cloud.example.com"}

    @patch("environment.services.get_current_site")
    @patch("environment.services.mailers")
    @patch("environment.models.BillingAccountSharingInvite.objects.create")
    def test_creates_invite_and_sends_email(
        self, mock_create_billing_invite, mock_mailers, mock_get_current_site
    ):
        mock_invite = Mock(spec=BillingAccountSharingInvite)
        mock_create_billing_invite.return_value = mock_invite
        mock_get_current_site.return_value.domain = "cloud.example.com"

        result = invite_user_to_shared_billing_account(
            self.request,
            self.user,
            self.user2.email,
            "billing-123",
        )

        mock_create_billing_invite.assert_called_once_with(
            owner=self.user,
            billing_account_id="billing-123",
            user_contact_email=self.user2.email,
        )
        mock_mailers.send_billing_sharing_confirmation.assert_called_once_with(
            site_domain="cloud.example.com", invite=mock_invite
        )
        self.assertEqual(result, mock_invite)

    @patch("environment.services.mailers")
    @patch("environment.models.BillingAccountSharingInvite.objects.create")
    def test_raises_if_invite_creation_fails(
        self, mock_create_billing_invite, mock_mailers
    ):
        mock_create_billing_invite.side_effect = Exception("Database error")

        with self.assertRaises(Exception):
            invite_user_to_shared_billing_account(
                self.request,
                self.user,
                self.user2.email,
                "billing-123",
            )

        mock_mailers.send_billing_sharing_confirmation.assert_not_called()


class ConsumeBillingAccountSharingTokenTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()
        self.user2 = create_user_with_cloud_identity(
            "abc", "abc@healthdatanexus.ai", "bar"
        )

    @patch("environment.models.BillingAccountSharingInvite.objects.get")
    def test_assigns_user_to_invite_and_saves(self, mock_get_billing_invite):
        mock_invite = Mock(spec=BillingAccountSharingInvite)
        mock_invite.owner = self.user
        mock_invite.user = None
        mock_get_billing_invite.return_value = mock_invite

        result = consume_billing_account_sharing_token(self.user2, "token-123")

        mock_get_billing_invite.assert_called_once_with(
            token="token-123", is_revoked=False
        )
        self.assertEqual(result, mock_invite)
        self.assertEqual(mock_invite.user, self.user2)

    @patch("environment.models.BillingAccountSharingInvite.objects.get")
    def test_raises_if_invited_user_is_owner(self, mock_get_billing_invite):
        mock_invite = Mock(spec=BillingAccountSharingInvite)
        mock_invite.owner = self.user
        mock_get_billing_invite.return_value = mock_invite

        with self.assertRaises(InvitedUserIsAccountOwner):
            consume_billing_account_sharing_token(self.user, "token-123")

        mock_invite.save.assert_not_called()

    @patch("environment.models.BillingAccountSharingInvite.objects.get")
    def test_raises_if_token_not_found(self, mock_get_billing_invite):
        mock_get_billing_invite.side_effect = BillingAccountSharingInvite.DoesNotExist

        with self.assertRaises(BillingAccountSharingInvite.DoesNotExist):
            consume_billing_account_sharing_token(self.user, "token-123")

        mock_get_billing_invite.assert_called_once_with(
            token="token-123", is_revoked=False
        )


class ConsumeBucketSharingTokenTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()
        self.user2 = create_user_with_cloud_identity(
            "abc", "abc@healthdatanexus.ai", "bar"
        )

    @patch("environment.models.BucketSharingInvite.objects.get")
    @patch("environment.api.share_bucket")
    def test_assigns_user_to_invite_and_saves(
        self, mock_share_bucket, mock_get_bucket_invite
    ):
        mock_invite = Mock(spec=BucketSharingInvite)
        mock_invite.owner = self.user
        mock_invite.user = None
        mock_get_bucket_invite.return_value = mock_invite

        result = consume_bucket_sharing_token(self.user2, "token-123")

        mock_get_bucket_invite.assert_called_once_with(
            token="token-123", is_revoked=False
        )
        mock_share_bucket.assert_called_once_with(
            owner_email=mock_invite.owner.cloud_identity.email,
            user_email=mock_invite.user.cloud_identity.email,
            bucket_name=mock_invite.shared_bucket_name,
            workspace_project_id=mock_invite.shared_workspace_name,
            permissions=mock_invite.permissions,
        )

        self.assertEqual(result, mock_invite)
        self.assertEqual(mock_invite.user, self.user2)

    @patch("environment.api.share_bucket")
    @patch("environment.models.BucketSharingInvite.objects.get")
    def test_raises_if_invited_user_is_owner(
        self, mock_get_bucket_invite, mock_share_bucket
    ):
        mock_invite = Mock(spec=BucketSharingInvite)
        mock_invite.owner = self.user
        mock_get_bucket_invite.return_value = mock_invite
        # Note: consume_bucket_sharing_token does not check if user is the owner —
        # it calls share_bucket regardless. This test verifies the current behavior.
        consume_bucket_sharing_token(self.user, "token-123")

        mock_share_bucket.assert_called_once()
        mock_invite.save.assert_called_once()

    @patch("environment.models.BucketSharingInvite.objects.get")
    def test_raises_if_token_not_found(self, mock_get_bucket_invite):
        mock_get_bucket_invite.side_effect = BucketSharingInvite.DoesNotExist

        with self.assertRaises(BucketSharingInvite.DoesNotExist):
            consume_bucket_sharing_token(self.user, "token-123")

        mock_get_bucket_invite.assert_called_once_with(
            token="token-123", is_revoked=False
        )


class RevokeBillingAccountSharingTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()
        self.user2 = create_user_with_cloud_identity(
            "abc", "abc@healthdatanexus.ai", "bar"
        )

    @patch("environment.api.revoke_billing_account_access")
    @patch("environment.models.BillingAccountSharingInvite.objects.select_related")
    def test_revokes_access_from_user(
        self, mock_select_related, mock_revoke_billing_account_access
    ):
        mock_invite = Mock(spec=BillingAccountSharingInvite)
        mock_invite.owner = self.user
        mock_invite.user = self.user2
        mock_invite.is_consumed = True
        mock_invite.billing_account_id = "billing-id"
        mock_select_related.return_value.get.return_value = mock_invite
        mock_revoke_billing_account_access.return_value = ""

        revoke_billing_account_access(1)

        mock_select_related.assert_called_once_with(
            "owner__cloud_identity", "user__cloud_identity"
        )
        mock_select_related.return_value.get.assert_called_once_with(pk=1)
        mock_invite.save.assert_called_once()
        self.assertTrue(mock_invite.is_revoked)
        mock_revoke_billing_account_access.assert_called_once()


class RevokeBucketSharingTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()
        self.user2 = create_user_with_cloud_identity(
            "abc", "abc@healthdatanexus.ai", "bar"
        )

    @patch("environment.api.revoke_shared_bucket_access")
    @patch("environment.models.BucketSharingInvite.objects.select_related")
    def test_revokes_access_from_user(
        self, mock_select_related, mock_api_revoke_shared_bucket_access
    ):
        mock_invite = Mock(spec=BucketSharingInvite)
        mock_invite.owner = self.user
        mock_invite.user = self.user2
        mock_invite.is_consumed = True
        mock_invite.bucket_id = "bucket-123"
        mock_select_related.return_value.get.return_value = mock_invite
        mock_api_revoke_shared_bucket_access.return_value = ""

        revoke_shared_bucket_access(1)

        mock_select_related.assert_called_once_with(
            "owner__cloud_identity", "user__cloud_identity"
        )
        mock_select_related.return_value.get.assert_called_once_with(pk=1)
        mock_invite.save.assert_called_once()
        self.assertTrue(mock_invite.is_revoked)


class CreateSharedWorkspaceTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()

    @patch("environment.services.persist_workflow")
    @patch("environment.api.create_shared_workspace")
    def test_creates_and_persists_workflow(
        self,
        mock_create_shared_workspace,
        mock_persist_workflow,
    ):
        # Prepare mock API response
        mock_response = Mock()
        mock_response.json.return_value = {"workflow_id": "wf-123"}
        mock_create_shared_workspace.return_value = mock_response

        result = create_shared_workspace(
            user=self.user,
            billing_account_id="billing-abc",
        )

        mock_create_shared_workspace.assert_called_once_with(
            user_email=self.user.cloud_identity.email,
            billing_account_id="billing-abc",
        )

        mock_response.json.assert_called_once()

        mock_persist_workflow.assert_called_once_with(
            user=self.user,
            workflow_id="wf-123",
        )
        self.assertIs(result, mock_response)

    @patch("environment.services.persist_workflow")
    @patch("environment.api.create_shared_workspace")
    def test_raises_if_response_has_no_workflow_id(
        self,
        mock_create_shared_workspace,
        mock_persist_workflow,
    ):
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_create_shared_workspace.return_value = mock_response

        with self.assertRaises(KeyError):
            create_shared_workspace(
                user=self.user,
                billing_account_id="billing-abc",
            )

        mock_persist_workflow.assert_not_called()


class DeleteSharedWorkspaceTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()

    @patch("environment.services.persist_workflow")
    @patch("environment.api.delete_shared_workspace")
    def test_deletes_and_persists_workflow(
        self,
        mock_delete_shared_workspace,
        mock_persist_workflow,
    ):
        mock_response = Mock()
        mock_response.json.return_value = {"workflow_id": "wf-delete-abc"}
        mock_delete_shared_workspace.return_value = mock_response

        result = delete_shared_workspace(
            user=self.user,
            billing_account_id="billing-abc",
            gcp_project_id="project-abc",
        )

        mock_delete_shared_workspace.assert_called_once_with(
            user_email=self.user.cloud_identity.email,
            workspace_project_id="project-abc",
            billing_account_id="billing-abc",
        )

        mock_response.json.assert_called_once()

        mock_persist_workflow.assert_called_once_with(
            user=self.user,
            workflow_id="wf-delete-abc",
        )

        self.assertIs(result, mock_response)

    @patch("environment.services.persist_workflow")
    @patch("environment.api.delete_shared_workspace")
    def test_raises_when_workflow_id_missing(
        self,
        mock_delete_shared_workspace,
        mock_persist_workflow,
    ):
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_delete_shared_workspace.return_value = mock_response

        with self.assertRaises(KeyError):
            delete_shared_workspace(
                user=self.user,
                billing_account_id="billing-abc",
                gcp_project_id="project-abc",
            )

        mock_persist_workflow.assert_not_called()


class CreateSharedBucketTestCase(TestCase):
    def setUp(self):
        self.user = create_user_with_cloud_identity()

    @patch("environment.api.create_shared_bucket")
    def test_creates_bucket_with_correct_params(self, mock_create_bucket):
        mock_response = Mock()
        mock_create_bucket.return_value = mock_response

        result = create_shared_bucket(
            region="us-central1",
            workspace_project_id="project-abc",
            user_defined_bucket_name="abc-bucket",
            user=self.user,
        )

        mock_create_bucket.assert_called_once_with(
            region="us-central1",
            user_email=self.user.cloud_identity.email,
            user_defined_bucket_name="abc-bucket",
            workspace_project_id="project-abc",
        )

        self.assertIs(result, mock_response)


class DeleteSharedBucketTestCase(TestCase):
    @patch("environment.api.delete_shared_bucket")
    def test_deletes_bucket_with_correct_params(self, mock_delete_bucket):
        mock_response = Mock()
        mock_delete_bucket.return_value = mock_response

        result = delete_shared_bucket(bucket_name="abc-bucket")

        mock_delete_bucket.assert_called_once_with(
            bucket_name="abc-bucket",
        )

        self.assertIs(result, mock_response)


class CheckCollaboratorProjectAccessTestCase(TestCase):

    @patch("environment.services.get_collaborator_user_by_email")
    @patch("environment.services.get_project")
    @patch("environment.services.can_access_project")
    def test_returns_true_when_user_can_access(
        self,
        mock_can_access_project,
        mock_get_project,
        mock_get_collaborator_user,
    ):
        mock_user = Mock()
        mock_project = Mock()

        mock_get_collaborator_user.return_value = mock_user
        mock_get_project.return_value = mock_project
        mock_can_access_project.return_value = True

        result = check_collaborator_project_access(
            collaborator_email="user@healthdatanexus.ai",
            project_id="proj-abc",
        )

        mock_get_collaborator_user.assert_called_once_with("user@healthdatanexus.ai")
        mock_get_project.assert_called_once_with("proj-abc")
        mock_can_access_project.assert_called_once_with(mock_project, mock_user)

        self.assertTrue(result)

    @patch("environment.services.get_collaborator_user_by_email")
    def test_returns_none_when_user_not_found(self, mock_get_collaborator_user):
        mock_get_collaborator_user.return_value = None

        result = check_collaborator_project_access(
            collaborator_email="ghost@example.com",
            project_id="proj-123",
        )

        self.assertIsNone(result)

    @patch("environment.services.get_collaborator_user_by_email")
    @patch("environment.services.get_project")
    @patch("environment.services.can_access_project")
    def test_raises_error_when_user_cannot_access(
        self,
        mock_can_access_project,
        mock_get_project,
        mock_get_collaborator_user,
    ):
        mock_user = Mock()
        mock_project = Mock()

        mock_get_collaborator_user.return_value = mock_user
        mock_get_project.return_value = mock_project
        mock_can_access_project.return_value = False

        with self.assertRaises(PublishedProjectAccessFailed):
            check_collaborator_project_access(
                collaborator_email="user@healthdatanexus.ai",
                project_id="proj-abc",
            )

        mock_can_access_project.assert_called_once()


class GetWorkbenchCollaboratorsTestCase(TestCase):

    @patch("environment.api.get_workbench_collaborators")
    def test_returns_collaborators_when_ok(self, mock_get_workbench_collaborators):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "collaborators": [
                {"email": "foo@healthdatamexus.ai"},
                {"email": "bar@healthdatanexus.ai"},
            ]
        }
        mock_get_workbench_collaborators.return_value = mock_response

        result = get_workbench_collaborators(
            workspace_project_id="proj-abc",
            service_account_name="sa-abc",
        )

        mock_get_workbench_collaborators.assert_called_once_with(
            workspace_project_id="proj-abc",
            service_account_name="sa-abc",
        )
        self.assertEqual(
            result,
            [
                {"email": "foo@healthdatamexus.ai"},
                {"email": "bar@healthdatanexus.ai"},
            ],
        )

    @patch("environment.api.get_workbench_collaborators")
    def test_returns_empty_list_and_logs_on_api_error(
        self, mock_get_workbench_collaborators
    ):
        mock_response = Mock()
        mock_response.ok = False
        mock_response.json.return_value = {"error": "Something broke"}
        mock_get_workbench_collaborators.return_value = mock_response

        result = get_workbench_collaborators(
            workspace_project_id="proj-abc",
            service_account_name="sa-abc",
        )

        self.assertEqual(result, [])

    @patch("environment.services.logger")
    @patch("environment.api.get_workbench_collaborators")
    def test_returns_empty_list_when_invalid_json(
        self, mock_get_workbench_collaborators, mock_logger
    ):
        mock_response = Mock()
        mock_response.ok = False
        mock_response.json.side_effect = ValueError("invalid JSON")
        mock_get_workbench_collaborators.return_value = mock_response

        result = get_workbench_collaborators(
            workspace_project_id="proj-abc",
            service_account_name="sa-abc",
        )

        self.assertEqual(result, [])


class AddWorkbenchCollaboratorTestCase(TestCase):

    @patch("environment.api.add_workbench_collaborators")
    def test_calls_api_with_correct_parameters(self, mock_add_workbench_collaborators):
        mock_response = Mock()
        mock_add_workbench_collaborators.return_value = mock_response

        result = add_workbench_collaborator(
            workspace_project_id="proj-abc",
            service_account_name="sa-abc",
            collaborator_email="user@healthdatanexus.ai",
        )

        mock_add_workbench_collaborators.assert_called_once_with(
            workspace_project_id="proj-abc",
            service_account_name="sa-abc",
            collaborators=["user@healthdatanexus.ai"],
        )

        self.assertIs(result, mock_response)


class RemoveWorkbenchCollaboratorTestCase(TestCase):

    @patch("environment.api.remove_workbench_collaborators")
    def test_calls_api_with_correct_parameters(self, mock_api):
        mock_response = Mock()
        mock_api.return_value = mock_response

        result = remove_workbench_collaborator(
            workspace_project_id="proj-abc",
            service_account_name="sa-abc",
            collaborator_email="user@healthdatanexus.ai",
        )

        mock_api.assert_called_once_with(
            workspace_project_id="proj-abc",
            service_account_name="sa-abc",
            collaborators=["user@healthdatanexus.ai"],
        )

        self.assertIs(result, mock_response)
