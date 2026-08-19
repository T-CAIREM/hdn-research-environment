from unittest import skipIf
from unittest.mock import Mock

from django.conf import settings
from django.test import TestCase

from environment.tests.helpers import (
    create_user_with_cloud_identity,
    create_user_without_cloud_identity,
)
from environment.exceptions import InvalidApiResponse
from environment.utilities import (
    inner_join_iterators,
    left_join_iterators,
    user_has_cloud_identity,
    validated_json,
)


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class UserHasCloudIdentityTestCase(TestCase):
    def setUp(self):
        self.user_without_cloud_identity = create_user_without_cloud_identity()
        self.user_with_cloud_identity = create_user_with_cloud_identity(
            "laa", "loo", "lee"
        )

    def test_returns_false_for_user_without_cloud_identity(self):
        self.assertFalse(user_has_cloud_identity(self.user_without_cloud_identity))

    def test_returns_true_for_user_with_cloud_identity(self):
        self.assertTrue(user_has_cloud_identity(self.user_with_cloud_identity))


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class InnerJoinIteratorsTestCase(TestCase):
    def test_returns_lists_left_joined_on_keys(self):
        list1 = [
            {"id": 1, "data": "anything1"},
            {"id": 2, "data": "anything2"},
            {"id": 3, "data": "anything3"},
            {"id": 4, "data": "anything3"},
        ]
        key_list1 = lambda x: x["id"]
        list2 = [
            {"dataset": 3, "other_data": "anything1"},
            {"dataset": 2, "other_data": "anything2"},
            {"dataset": 5, "other_data": "anything3"},
        ]
        key_list2 = lambda x: x["dataset"]
        inner_joined = inner_join_iterators(key_list1, list1, key_list2, list2)
        expected_output = [
            (list1[1], list2[1]),
            (list1[2], list2[0]),
        ]
        self.assertEqual(inner_joined, expected_output)


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class LeftJoinIteratorsTestCase(TestCase):
    def test_returns_lists_left_joined_on_keys(self):
        list1 = [
            {"id": 1, "data": "anything1"},
            {"id": 2, "data": "anything2"},
            {"id": 3, "data": "anything3"},
            {"id": 4, "data": "anything3"},
        ]
        key_list1 = lambda x: x["id"]
        list2 = [
            {"dataset": 3, "other_data": "anything1"},
            {"dataset": 2, "other_data": "anything2"},
            {"dataset": 1, "other_data": "anything3"},
        ]
        key_list2 = lambda x: x["dataset"]
        left_joined = left_join_iterators(key_list1, list1, key_list2, list2)
        expected_output = [
            (list1[0], list2[2]),
            (list1[1], list2[1]),
            (list1[2], list2[0]),
            (list1[3], None),
        ]
        self.assertEqual(left_joined, expected_output)


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class ValidatedJsonTestCase(TestCase):
    """Regression tests for the 2026-08-19 /environments/ incident: an API 500
    error body was parsed as if it were the workspaces list."""

    def _response(self, ok=True, status_code=200, body=None):
        response = Mock()
        response.ok = ok
        response.status_code = status_code
        response.json.return_value = body
        return response

    def test_returns_parsed_body_on_success(self):
        response = self._response(body=[{"gcp_project_id": "p"}])
        self.assertEqual(
            validated_json(response, expect=list), [{"gcp_project_id": "p"}]
        )

    def test_raises_on_error_status_before_parsing(self):
        response = self._response(ok=False, status_code=500, body={"error": "boom"})
        with self.assertRaises(InvalidApiResponse) as ctx:
            validated_json(response, expect=list)
        self.assertIs(ctx.exception.response, response)

    def test_raises_on_wrong_top_level_shape(self):
        response = self._response(body={"error": "not a list"})
        with self.assertRaises(InvalidApiResponse):
            validated_json(response, expect=list)

    def test_raises_on_non_object_list_elements_when_requested(self):
        # A serializer bug upstream can inject non-dict elements into a 200.
        response = self._response(body=[{"gcp_project_id": "p"}, ["oops", {}]])
        with self.assertRaises(InvalidApiResponse):
            validated_json(response, expect=list, elements=dict)

    def test_accepts_mixed_elements_without_element_expectation(self):
        # The workspaces pipeline salvages entries individually, so the
        # transport check must not reject the whole batch.
        body = [{"gcp_project_id": "p"}, ["oops", {}]]
        response = self._response(body=body)
        self.assertEqual(validated_json(response, expect=list), body)

    def test_accepts_any_shape_without_expectation(self):
        response = self._response(body=None)
        self.assertIsNone(validated_json(response))
