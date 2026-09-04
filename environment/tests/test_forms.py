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

    def _build_form(self, active_projects_list=None, **overrides):
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
            active_projects_list=(
                [self.active_project]
                if active_projects_list is None
                else active_projects_list
            ),
        )

    def test_requires_a_project(self):
        form = self._build_form()
        form.is_valid()

        self.assertTrue(form.errors.get("project_id"))

    def test_accepts_a_published_project(self):
        form = self._build_form(project_id="published:1")
        form.is_valid()

        self.assertIsNone(form.errors.get("__all__"))
        self.assertIsNone(form.errors.get("project_id"))

    def test_accepts_an_active_project_on_jupyter(self):
        form = self._build_form(project_id="active:7")
        form.is_valid()

        self.assertIsNone(form.errors.get("__all__"))
        self.assertIsNone(form.errors.get("project_id"))

    def test_accepts_an_active_project_on_rstudio(self):
        form = self._build_form(project_id="active:7", environment_type="rstudio")
        form.is_valid()

        self.assertIsNone(form.errors.get("__all__"))
        self.assertIsNone(form.errors.get("project_id"))

    def test_rejects_an_active_project_outside_jupyter_or_rstudio(self):
        form = self._build_form(project_id="active:7", environment_type="collaborative")
        form.is_valid()

        self.assertEqual(
            form.errors.get("__all__"),
            [
                "Draft projects can only be attached to a Jupyter or RStudio environment."
            ],
        )

    def test_rejects_an_unlisted_project(self):
        form = self._build_form(project_id="active:1")
        form.is_valid()

        self.assertTrue(form.errors.get("project_id"))

    def test_groups_published_and_draft_choices(self):
        form = self._build_form()

        self.assertEqual(
            [
                (group, [value for value, _ in entries])
                for group, entries in form.fields["project_id"].choices
            ],
            [
                ("Published datasets", ["published:1"]),
                ("My draft projects (read/write)", ["active:7"]),
            ],
        )

    def test_omits_the_draft_group_without_draft_projects(self):
        form = self._build_form(active_projects_list=[])

        self.assertEqual(
            [group for group, _ in form.fields["project_id"].choices],
            ["Published datasets"],
        )
