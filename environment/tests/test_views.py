from unittest import skipIf
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from environment.entities import ResearchWorkspace, WorkspaceStatus
from environment.exceptions import (
    BillingVerificationFailed,
    GetAvailableEnvironmentsFailed,
)
from environment.tests.helpers import (
    create_user_with_cloud_identity,
    create_user_without_cloud_identity,
)
from environment.tests.test_services import ActiveProjectFixtureMixin


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class IdentityProvisioningTestCase(TestCase):
    url = reverse("identity_provisioning")

    def test_redirects_to_login_if_not_logged_in(self):
        response = self.client.get(self.url)
        redirect_url = f"{reverse('login')}?next={self.url}"
        self.assertRedirects(response, redirect_url)

    @patch("environment.services.create_cloud_identity")
    def test_redirects_after_successful_identity_creation(
        self, mock_create_cloud_identity
    ):
        user = create_user_without_cloud_identity()
        self.client.force_login(user=user)

        response = self.client.post(
            self.url,
            {
                "password": "Str0ng!Pass",
                "confirm_password": "Str0ng!Pass",
                "recovery_email": "recovery@example.com",
            },
        )
        mock_create_cloud_identity.assert_called_once()
        self.assertRedirects(
            response, reverse("research_environments"), fetch_redirect_response=False
        )


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class ResearchEnvironmentsTestCase(TestCase):
    url = reverse("research_environments")

    def test_redirects_to_login_if_not_logged_in(self):
        response = self.client.get(self.url)
        redirect_url = f"{reverse('login')}?next={self.url}"
        self.assertRedirects(response, redirect_url)

    def test_redirects_to_identity_provisioning_if_user_has_no_cloud_identity(self):
        user = create_user_without_cloud_identity()
        self.client.force_login(user=user)

        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("identity_provisioning"))

    @patch("environment.services.get_running_workflows")
    @patch("environment.services.get_shared_workspaces_list")
    @patch("environment.services.get_billing_accounts_list")
    @patch("environment.services.get_workspaces_list")
    def test_fetches_and_matches_available_environments_and_projects(
        self,
        mock_get_workspaces_list,
        mock_get_billing_accounts_list,
        mock_get_shared_workspaces_list,
        mock_get_running_workflows,
    ):
        mock_get_workspaces_list.return_value = []
        mock_get_billing_accounts_list.return_value = []
        mock_get_shared_workspaces_list.return_value = []
        mock_get_running_workflows.return_value = []

        user = create_user_with_cloud_identity()
        self.client.force_login(user=user)

        response = self.client.get(self.url)
        mock_get_workspaces_list.assert_called()
        mock_get_billing_accounts_list.assert_called()
        self.assertEqual(response.status_code, 200)


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class CreateResearchEnvironmentTestCase(TestCase):
    url = reverse(
        "create_research_environment",
        kwargs={"workspace_id": "some_workspace_id"},
    )

    def test_redirects_to_login_if_not_logged_in(self):
        response = self.client.get(self.url)
        redirect_url = f"{reverse('login')}?next={self.url}"
        self.assertRedirects(response, redirect_url)

    def test_redirects_to_identity_provisioning_if_user_has_no_cloud_identity(self):
        user = create_user_without_cloud_identity()
        self.client.force_login(user=user)

        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("identity_provisioning"))


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class ResearchEnvironmentsApiFailureTestCase(TestCase):
    """An API failure must degrade the environments page, not 500 it
    (regression for the 2026-08-19 incident)."""

    def setUp(self):
        self.user = create_user_with_cloud_identity()
        self.client.force_login(user=self.user)

    def _patch_services(self):
        billing_accounts = [{"id": "b-1", "name": "Billing One"}]
        return (
            patch(
                "environment.services.get_workspaces_list",
                side_effect=GetAvailableEnvironmentsFailed("API unavailable"),
            ),
            patch(
                "environment.services.get_billing_accounts_list",
                return_value=billing_accounts,
            ),
            patch("environment.services.get_shared_workspaces_list", return_value=[]),
            billing_accounts,
        )

    def test_failed_section_degrades_only_itself(self):
        p1, p2, p3, billing_accounts = self._patch_services()
        with p1, p2, p3:
            response = self.client.get(reverse("research_environments"))

        # The page renders; only the workspaces section is empty and flagged.
        self.assertEqual(response.status_code, 200)
        messages = [str(m) for m in response.context["messages"]]
        self.assertTrue(any("API unavailable" in m for m in messages))
        self.assertEqual(response.context["workspaces_with_workbenches"], [])
        self.assertEqual(response.context["billing_accounts_list"], billing_accounts)

    def test_partial_returns_503_when_api_fails(self):
        p1, p2, p3, _ = self._patch_services()
        with p1, p2, p3:
            response = self.client.get(reverse("research_environments_partial"))

        # The polling JS keeps the current cards when the refresh is not ok.
        self.assertEqual(response.status_code, 503)


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class CreateResearchEnvironmentDraftChoicesTestCase(
    ActiveProjectFixtureMixin, TestCase
):
    """The creation dropdown and POST honour the draft-workbenches setting."""

    DRAFT_GROUP = "My draft projects (read/write)"

    def setUp(self):
        self.user = create_user_with_cloud_identity()
        self.client.force_login(user=self.user)
        self.draft = self._create_draft_for(self.user)
        self.url = reverse(
            "create_research_environment", kwargs={"workspace_id": "ws-1"}
        )
        workspace = ResearchWorkspace(
            gcp_project_id="ws-1",
            gcp_billing_id="billing-1",
            status=WorkspaceStatus.CREATED,
            is_owner=True,
            workbenches=[],
        )
        patchers = (
            patch("environment.services.get_workspaces_list", return_value=[workspace]),
            patch("environment.services.get_shared_workspaces_list", return_value=[]),
        )
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _choice_groups(self, response):
        return {
            group: [value for value, _label in entries]
            for group, entries in response.context["form"].fields["project_id"].choices
        }

    @override_settings(CLOUD_RESEARCH_ENVIRONMENTS_ENABLE_DRAFT_WORKBENCHES=False)
    def test_offers_only_published_projects_while_disabled(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.DRAFT_GROUP, self._choice_groups(response))

    @override_settings(CLOUD_RESEARCH_ENVIRONMENTS_ENABLE_DRAFT_WORKBENCHES=False)
    @patch("environment.services.create_research_environment")
    def test_rejects_a_draft_selection_while_disabled(self, mock_create):
        response = self.client.post(
            self.url,
            {
                "project_id": f"active:{self.draft.id}",
                "environment_type": "jupyter",
                "machine_type": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors.get("project_id"))
        mock_create.assert_not_called()

    @override_settings(CLOUD_RESEARCH_ENVIRONMENTS_ENABLE_DRAFT_WORKBENCHES=True)
    def test_offers_editable_drafts_when_enabled(self):
        self._accept_upload_agreement(self.draft, self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._choice_groups(response)[self.DRAFT_GROUP],
            [f"active:{self.draft.id}"],
        )
        self.assertEqual(response.context["drafts_awaiting_upload_agreement"], [])

    @override_settings(
        CLOUD_RESEARCH_ENVIRONMENTS_ENABLE_DRAFT_WORKBENCHES=True,
        UPLOAD_AGREEMENT_START_DATE=None,
    )
    def test_links_drafts_that_await_the_upload_agreement(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.DRAFT_GROUP, self._choice_groups(response))
        agreement_url = reverse("project_upload_agreement", args=(self.draft.slug,))
        self.assertContains(response, f'href="{agreement_url}"')
        self.assertContains(response, "accept the upload agreement")

    @override_settings(
        CLOUD_RESEARCH_ENVIRONMENTS_ENABLE_DRAFT_WORKBENCHES=True,
        UPLOAD_AGREEMENT_START_DATE=None,
    )
    @patch("environment.services.create_research_environment")
    def test_rejects_a_draft_that_awaits_the_upload_agreement(self, mock_create):
        response = self.client.post(
            self.url,
            {
                "project_id": f"active:{self.draft.id}",
                "environment_type": "jupyter",
                "machine_type": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors.get("project_id"))
        mock_create.assert_not_called()
