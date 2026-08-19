from unittest import skipIf
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from environment.exceptions import (
    BillingVerificationFailed,
    GetAvailableEnvironmentsFailed,
)
from environment.tests.helpers import (
    create_user_with_cloud_identity,
    create_user_without_cloud_identity,
)


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
