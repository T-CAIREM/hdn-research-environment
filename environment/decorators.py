import logging
from functools import wraps
from typing import Callable

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db.models import Model
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

from environment.utilities import (
    _handle_api_error,
    user_has_access_billing_account,
    user_has_cloud_identity,
)

View = Callable[[HttpRequest], HttpResponse]

User = Model


def _redirect_view_if_user(
    predicate: Callable[[User], bool], redirect_url: str, message: str = None
):
    def wrapper(view: View) -> View:
        @wraps(view)
        def wrapped_view(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            if predicate(request.user):
                if message:
                    messages.info(request, message)
                return redirect(redirect_url)
            return view(request, *args, **kwargs)

        return wrapped_view

    return wrapper


def console_permission_required(perm):
    # decorator from physionet to add  required permissions to views -
    # they are needed to properly handle admin console views
    def wrapper(view):
        view = permission_required(perm, raise_exception=True)(view)
        view.required_permission = perm
        return view

    return wrapper


cloud_identity_required = _redirect_view_if_user(
    lambda u: not user_has_cloud_identity(u), "identity_provisioning"
)


def _user_has_billing_account_access(user):
    """Check if user has billing account access. Local import to avoid circular dependency."""
    from environment.services import get_billing_accounts_list

    return user_has_access_billing_account(get_billing_accounts_list(user))


billing_account_required = _redirect_view_if_user(
    lambda u: not _user_has_billing_account_access(u),
    "research_environments",
    "You have to have access to at least one billing account in order to create a workspace. Visit the Billing tab for more information.",
)


require_PATCH = require_http_methods(["PATCH"])


require_DELETE = require_http_methods(["DELETE"])


require_POST = require_http_methods(["POST"])


logger = logging.getLogger(__name__)


def handle_api_error(
    operation_name: str,
    exception_class,
    additional_context_func: Callable = None,
):
    """
    Decorator that handles API errors automatically.

    IMPORTANT: This decorator ONLY handles errors. It always returns the raw Response object.
    The decorated function is responsible for calling response.json() when needed.

    Args:
        operation_name: Human-readable name of the operation
        exception_class: The exception class to raise on error
        additional_context_func: Optional function that takes function args/kwargs and returns additional context dict

    The decorated function must return a response object with .ok attribute.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            response = func(*args, **kwargs)

            # Check if response indicates an error
            if hasattr(response, "ok") and not response.ok:
                # Prepare additional context
                additional_context = {}
                if additional_context_func:
                    try:
                        additional_context = additional_context_func(*args, **kwargs)
                    except Exception as e:
                        logger.warning(
                            f"Failed to generate additional context for {operation_name}: {e}"
                        )

                # Use existing error handler
                _handle_api_error(
                    response, operation_name, exception_class, additional_context
                )

            # Always return the raw response - function handles JSON parsing
            return response

        return wrapper

    return decorator
