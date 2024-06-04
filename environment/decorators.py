from functools import wraps
from typing import Callable
from django.contrib import messages

from django.db.models import Model
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import permission_required

from environment.services import get_billing_accounts_list

from environment.utilities import (
    user_has_cloud_identity,
    user_has_access_billing_account,
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

billing_account_required = _redirect_view_if_user(
    lambda u: not user_has_access_billing_account(get_billing_accounts_list(u)),
    "research_environments",
    "You have to have access to at least one billing account in order to create a workspace. Visit the Billing tab for more information.",
)


require_PATCH = require_http_methods(["PATCH"])


require_DELETE = require_http_methods(["DELETE"])
