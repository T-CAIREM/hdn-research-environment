from unittest import skipIf
from unittest.mock import Mock

from django.conf import settings
from django.test import TestCase

from environment.forms import CreateResearchEnvironmentForm


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class CreateResearchEnvironmentFormTestCase(TestCase):
    def setUp(self):
        self.workspace = Mock()
        self.workspace.gcp_project_id = "workspace-123"
        self.project = Mock()
        self.project.id = 1
        self.active_project = Mock()
        self.active_project.id = 7

    def _build_form(self, **overrides):
        data = {
            "region": "us-central1",
            "machine_type": "1",
            "environment_type": "jupyter",
            "disk_size": 0,
        }
        data.update(overrides)
        return CreateResearchEnvironmentForm(
            data,
            selected_workspace=self.workspace,
            projects_list=[self.project],
            buckets_list=[],
            active_projects_list=[self.active_project],
        )

    def test_requires_a_project(self):
        form = self._build_form()
        form.is_valid()

        self.assertTrue(form.errors.get("__all__"))

    def test_rejects_both_a_published_and_an_active_project(self):
        form = self._build_form(project_id="1", active_project_id="7")
        form.is_valid()

        self.assertTrue(form.errors.get("__all__"))

    def test_accepts_a_published_project_alone(self):
        form = self._build_form(project_id="1")
        form.is_valid()

        self.assertIsNone(form.errors.get("__all__"))

    def test_accepts_an_active_project_alone(self):
        form = self._build_form(active_project_id="7")
        form.is_valid()

        self.assertIsNone(form.errors.get("__all__"))

    def test_rejects_an_active_project_outside_jupyter(self):
        form = self._build_form(active_project_id="7", environment_type="rstudio")
        form.is_valid()

        self.assertTrue(form.errors.get("__all__"))
