from unittest import skipIf
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from environment.exceptions import BillingVerificationFailed
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
