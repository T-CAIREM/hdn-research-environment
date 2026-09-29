from unittest import skipIf
from unittest.mock import patch

from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from environment.entities import (
    EnvironmentStatus,
    EnvironmentType,
    Region,
    ResearchEnvironment,
)
from environment.templatetags.action_buttons import button_types
from environment.tests.helpers import create_user_with_cloud_identity


def _environment() -> ResearchEnvironment:
    return ResearchEnvironment(
        gcp_identifier="wb-1",
        dataset_identifier="demoproject100",
        url=None,
        workspace_name="proj-123",
        status=EnvironmentStatus.RUNNING,
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


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class EnvironmentActionButtonLoadingStateTestCase(SimpleTestCase):
    """Pause, start and the other workbench actions show they are busy once clicked."""

    def _render(self, button_type):
        return Template(
            "{% load action_buttons %}"
            "{% environment_action_button environment=environment button_type=button_type %}"
        ).render(Context({"environment": _environment(), "button_type": button_type}))

    def test_pause_and_start_carry_their_busy_labels(self):
        for button_type, loading_text in (
            ("pause", "Pausing…"),
            ("start", "Starting…"),
        ):
            with self.subTest(button_type=button_type):
                html = self._render(button_type)

                self.assertIn(f'data-loading-text="{loading_text}"', html)
                # The clicked button is handed to sendRequest so only it spins.
                self.assertIn(f"'{button_type}', this)", html)

    def test_spinner_is_hidden_until_clicked_and_announced_politely(self):
        html = self._render("pause")

        self.assertIn(
            '<span class="action-button-spinner" aria-hidden="true" hidden></span>',
            html,
        )
        self.assertIn('<span class="action-button-label">Pause</span>', html)
        self.assertIn(
            '<span class="action-button-status sr-only" role="status"></span>', html
        )

    def test_every_workbench_action_has_a_busy_label(self):
        for button_type, data in button_types.items():
            if "url_name" in data:
                with self.subTest(button_type=button_type):
                    self.assertTrue(data["loading_text"].endswith("…"))


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class ResearchEnvironmentsPageLoadingStateTestCase(TestCase):
    @patch("environment.services.get_running_workflows", return_value=[])
    @patch("environment.services.get_shared_workspaces_list", return_value=[])
    @patch("environment.services.get_billing_accounts_list", return_value=[])
    @patch("environment.services.get_workspaces_list", return_value=[])
    def test_page_ships_the_loading_state_script_and_style(self, *_mocks):
        self.client.force_login(user=create_user_with_cloud_identity())

        response = self.client.get(reverse("research_environments"))

        self.assertContains(
            response, "function setActionButtonLoading(button, loading)"
        )
        self.assertContains(response, "setActionButtonLoading(button, true);")
        self.assertContains(response, "setActionButtonLoading(button, false);")
        self.assertContains(response, 'attr("aria-busy", "true")')
        self.assertContains(response, "@media (prefers-reduced-motion: reduce)")
