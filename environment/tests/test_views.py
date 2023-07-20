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
    def test_saves_one_time_password_in_session(self, mock_create_cloud_identity):
        otp = "otp"
        mock_create_cloud_identity.return_value = (otp, "identity object")
        user = create_user_without_cloud_identity()
        self.client.force_login(user=user)

        self.client.post(self.url)
        self.assertEqual(self.client.session["cloud_identity_otp"], otp)


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

    @patch("environment.services.get_available_projects_with_environments")
    @patch("environment.services.get_environments_with_projects")
    def test_fetches_and_matches_available_environments_and_projects(
        self,
        mock_get_available_projects_with_environments,
        mock_get_environments_with_projects,
    ):
        user = create_user_with_cloud_identity()
        self.client.force_login(user=user)

        response = self.client.get(self.url)
        mock_get_environments_with_projects.assert_called()
        mock_get_available_projects_with_environments.assert_called()
        self.assertEqual(response.status_code, 200)


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class CreateResearchEnvironmentTestCase(TestCase):
    url = reverse(
        "create_research_environment",
        kwargs={"project_slug": "some_slug", "project_version": "some_version"},
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
