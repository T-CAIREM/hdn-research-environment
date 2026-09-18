"""Regression coverage for deployments outside healthdatanexus.ai (#182)."""

from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings

from environment.config import get_organization_domain, get_support_email
from environment.entities import WorkspaceStatus
from environment.exceptions import CreateSharedBucketFailed
from environment.views import create_shared_bucket


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "base.html": (
                            "{% block local_js_top %}{% endblock %}"
                            "{% block content %}{% endblock %}"
                        ),
                        "message_snippet.html": "",
                    },
                ),
                "django.template.loaders.app_directories.Loader",
            ]
        },
    }
]


@override_settings(
    TEMPLATES=TEMPLATES,
    SITE_NAME="PhysioNet",
    CONTACT_EMAIL="PhysioNet Support <help@physionet.org>",
    CLOUD_RESEARCH_ENVIRONMENTS_ORGANIZATION_DOMAIN="",
)
class DeploymentTemplateTests(SimpleTestCase):
    def setUp(self):
        self.user = SimpleNamespace(
            username="owner",
            cloud_identity=SimpleNamespace(email="owner@physionet.org"),
        )

    def render_collaborator_page(self, template):
        """Render each form with the same non-HDN owner and collaborators."""
        return render_to_string(
            f"environment/{template}.html",
            {
                "user": self.user,
                "selected_workspace": {"gcp_project_id": "workspace"},
                "workbench_owner_username": "owner",
                "collaborators": [
                    "owner@physionet.org",
                    "colleague@physionet.org",
                    "owner@another.org",
                ],
            },
        )

    def test_collaborator_forms_use_cloud_identity_domain(self):
        for template in (
            "create_research_environment",
            "manage_collaborative_environment",
        ):
            with self.subTest(template=template):
                html = self.render_collaborator_page(template)
                self.assertIn('data-organization-domain="physionet.org"', html)
                self.assertIn("Email must end with @physionet.org", html)
                self.assertNotIn("healthdatanexus.ai", html)

    @override_settings(
        CLOUD_RESEARCH_ENVIRONMENTS_ORGANIZATION_DOMAIN=" @Research.Example "
    )
    def test_explicit_domain_overrides_identity_domain(self):
        for template in (
            "create_research_environment",
            "manage_collaborative_environment",
        ):
            with self.subTest(template=template):
                html = self.render_collaborator_page(template)
                self.assertIn('data-organization-domain="research.example"', html)
                self.assertIn("Email must end with @research.example", html)

    def test_owner_has_no_remove_control(self):
        html = self.render_collaborator_page("manage_collaborative_environment")
        self.assertNotIn('name="collaborator_email" value="owner@physionet.org"', html)
        self.assertIn('name="collaborator_email" value="colleague@physionet.org"', html)
        self.assertIn('name="collaborator_email" value="owner@another.org"', html)

    def test_owner_email_comparison_is_case_insensitive(self):
        self.user.cloud_identity.email = "OWNER@PHYSIONET.ORG"
        html = self.render_collaborator_page("manage_collaborative_environment")
        self.assertNotIn('name="collaborator_email" value="owner@physionet.org"', html)

    def test_missing_cloud_identity_does_not_invent_a_domain(self):
        self.user = SimpleNamespace(username="owner")
        self.assertEqual(get_organization_domain(self.user), "")
        self.assertEqual(get_organization_domain(), "")
        html = self.render_collaborator_page("create_research_environment")
        self.assertIn('data-organization-domain=""', html)
        self.assertNotIn("Email must end with @", html)

    def test_billing_instructions_use_site_name(self):
        html = render_to_string("environment/_billing_accounts_list.html")
        self.assertIn("log in to PhysioNet", html)
        self.assertNotIn("Health Data Nexus", html)

    def test_bucket_errors_use_contact_email_without_display_name(self):
        html = render_to_string(
            "environment/bucket_files_form.html", {"workspace_has_errors": True}
        )
        self.assertIn('href="mailto:help@physionet.org"', html)
        self.assertNotIn("support@healthdatanexus.ai", html)

    @override_settings(SUPPORT_EMAIL="Help Desk <support@research.example>")
    def test_support_email_takes_precedence(self):
        html = render_to_string(
            "environment/bucket_files_form.html", {"workspace_has_errors": True}
        )
        self.assertIn('href="mailto:support@research.example"', html)
        self.assertNotIn("help@physionet.org", html)

    @override_settings(
        SUPPORT_EMAIL="", CONTACT_EMAIL="", DEFAULT_FROM_EMAIL="Site <site@example.org>"
    )
    def test_support_email_falls_back_to_sender(self):
        self.assertEqual(get_support_email(), "site@example.org")

    def test_bucket_creation_error_uses_configured_support_address(self):
        request = RequestFactory().post("/environments/sharing/bucket/create/workspace")
        request.user = self.user
        request.user.is_authenticated = True
        workspace = SimpleNamespace(
            gcp_project_id="workspace", status=WorkspaceStatus.CREATED
        )
        with (
            patch(
                "environment.services.get_shared_workspaces_list",
                return_value=[workspace],
            ),
            patch("environment.views.CreateSharedBucketForm") as form,
            patch(
                "environment.services.create_shared_bucket",
                side_effect=CreateSharedBucketFailed("Unavailable"),
            ),
            patch("environment.views.messages.error") as message,
            patch("environment.views.render", return_value=HttpResponse()) as render,
        ):
            form.return_value.is_valid.return_value = True
            form.return_value.cleaned_data = {
                "region": "region",
                "user_defined_bucket_name": "bucket",
                "workspace_project_id": "workspace",
            }

            response = create_shared_bucket(request, "workspace")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Please contact help@physionet.org", message.call_args.args[1])
        self.assertIn("Unavailable", message.call_args.args[1])
        render.assert_called_once()
