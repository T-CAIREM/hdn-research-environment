from unittest import skipIf
from unittest.mock import Mock, patch

import requests
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from environment import api
from environment.api.decorators import API_REQUEST_TIMEOUT_SECONDS

from environment.decorators import (
    cloud_identity_required,
    handle_api_error,
    require_DELETE,
    require_PATCH,
)


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class CloudIdentityRequiredTestCase(TestCase):
    def test_redirects_user_without_cloud_identity_to_identity_provisioning(self):
        request_with_user_without_cloud_identity = Mock(
            user=Mock(spec=[]),
        )
        view = Mock()
        decorated_view = cloud_identity_required(view)
        response = decorated_view(request_with_user_without_cloud_identity)
        self.assertRedirects(
            response, reverse("identity_provisioning"), fetch_redirect_response=False
        )
        view.assert_not_called()

    def test_does_not_redirect_user_with_cloud_identity(self):
        request_with_user_without_cloud_identity = Mock(
            user=Mock(spec=["cloud_identity"]),
        )
        view = Mock()
        decorated_view = cloud_identity_required(view)
        decorated_view(request_with_user_without_cloud_identity)
        view.assert_called()


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class RequirePatchTestCase(TestCase):
    def test_returns_405_for_non_patch_requests(self):
        methods = [
            "DELETE",
            "GET",
            "POST",
            "HEAD",
            "PUT",
            "CONNECT",
            "OPTIONS",
            "TRACE",
        ]
        responses = []
        for method in methods:
            request = Mock(method=method)
            view = Mock()
            decorated_view = require_PATCH(view)
            responses.append(decorated_view(request))
        self.assertTrue(all(response.status_code == 405 for response in responses))

    def test_succeeds_for_patch_request(self):
        request = Mock(method="PATCH")
        view = Mock()
        decorated_view = require_PATCH(view)
        decorated_view(request)
        view.assert_called()


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class RequireDeleteTestCase(TestCase):
    def test_returns_405_for_non_delete_requests(self):
        methods = ["PATCH", "GET", "POST", "HEAD", "PUT", "CONNECT", "OPTIONS", "TRACE"]
        responses = []
        for method in methods:
            request = Mock(method=method)
            view = Mock()
            decorated_view = require_DELETE(view)
            responses.append(decorated_view(request))
        self.assertTrue(all(response.status_code == 405 for response in responses))

    def test_succeeds_for_delete_request(self):
        request = Mock(method="DELETE")
        view = Mock()
        decorated_view = require_DELETE(view)
        decorated_view(request)
        view.assert_called()


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class HandleApiErrorTestCase(TestCase):
    class OperationFailed(Exception):
        pass

    def test_returns_response_from_decorated_function_on_success(self):
        response = Mock(ok=True)
        decorated = handle_api_error("Test Operation", self.OperationFailed)(
            lambda: response
        )
        self.assertIs(decorated(), response)

    def test_raises_domain_exception_when_function_parses_non_json_response(self):
        def parse_load_balancer_error_page():
            raise requests.exceptions.JSONDecodeError(
                "Expecting value", "\n<html></html>", 1
            )

        decorated = handle_api_error("Test Operation", self.OperationFailed)(
            parse_load_balancer_error_page
        )
        with self.assertRaises(self.OperationFailed):
            decorated()


@skipIf(
    not settings.ENABLE_CLOUD_RESEARCH_ENVIRONMENTS,
    "Research environments are disabled",
)
class ApiRequestTimeoutTestCase(TestCase):
    @patch("environment.api.decorators._apply_api_credentials")
    @patch("environment.api.decorators.Session.send")
    def test_api_calls_are_sent_with_a_timeout(self, mock_send, _mock_credentials):
        api.share_billing_account(
            owner_email="owner@example.com",
            user_email="user@example.com",
            billing_account_id="012345-6789AB-CDEF01",
        )

        self.assertEqual(
            mock_send.call_args.kwargs["timeout"], API_REQUEST_TIMEOUT_SECONDS
        )

    def test_timeout_outlasts_the_api_billing_retry_budget(self):
        # The API retries a conflicting billing share for about 35 s at worst.
        self.assertGreater(API_REQUEST_TIMEOUT_SECONDS, 35)
