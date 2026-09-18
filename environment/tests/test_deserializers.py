import uuid
from unittest import skipIf
from unittest.mock import Mock

from django.conf import settings
from django.test import TestCase

from environment.deserializers import (
    _active_project_data_group,
    _group_for,
    _project_data_group,
    is_draft_identifier,
)


def _project_mock(model_name: str) -> Mock:
    project = Mock()
    project._meta.model_name = model_name
    return project


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class ProjectDataGroupTestCase(TestCase):
    def test_active_project_group_is_the_core_project_uuid(self):
        project = _project_mock("activeproject")
        project.core_project_id = uuid.UUID("2b0e0b1e6b3f4a5c8d9e0f1a2b3c4d5e")

        self.assertEqual(
            _active_project_data_group(project),
            "a2b0e0b1e6b3f4a5c8d9e0f1a2b3c4d5e",
        )

    def test_group_for_dispatches_on_the_model(self):
        active_project = _project_mock("activeproject")
        active_project.core_project_id = uuid.uuid4()
        published_project = _project_mock("publishedproject")
        published_project.slug = "demo-project"
        published_project.version = "1.0.0"

        self.assertEqual(
            _group_for(active_project), _active_project_data_group(active_project)
        )
        self.assertEqual(
            _group_for(published_project), _project_data_group(published_project)
        )


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class IsDraftIdentifierTestCase(TestCase):
    def test_matches_an_identifier_minted_for_an_active_project(self):
        project = _project_mock("activeproject")
        project.core_project_id = uuid.uuid4()

        self.assertTrue(is_draft_identifier(_active_project_data_group(project)))

    def test_matches_a_lowercase_hex_uuid_behind_the_a_prefix(self):
        self.assertTrue(is_draft_identifier("a2b0e0b1e6b3f4a5c8d9e0f1a2b3c4d5e"))

    def test_rejects_published_identifiers(self):
        published_project = _project_mock("publishedproject")
        published_project.slug = "demo-project"
        published_project.version = "1.0.0"

        self.assertFalse(is_draft_identifier(_project_data_group(published_project)))
        # A published slug that happens to start with "a" is still not a draft.
        self.assertFalse(is_draft_identifier("addataset100"))

    def test_rejects_near_misses(self):
        hex32 = "2b0e0b1e6b3f4a5c8d9e0f1a2b3c4d5e"

        self.assertFalse(is_draft_identifier(""))
        self.assertFalse(is_draft_identifier(None))
        self.assertFalse(is_draft_identifier(hex32))  # no "a" prefix
        self.assertFalse(is_draft_identifier("a" + hex32[:-1]))  # too short
        self.assertFalse(is_draft_identifier("a" + hex32 + "0"))  # too long
        self.assertFalse(is_draft_identifier("a" + hex32.upper()))  # uppercase hex
        self.assertFalse(is_draft_identifier("b" + hex32))  # wrong prefix
        self.assertFalse(is_draft_identifier("a" + hex32 + "\n"))  # trailing newline
