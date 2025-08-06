from collections import namedtuple
import json


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth import get_user_model
from environment.forms import (
    CreateWorkspaceForm,
    CreateSharedWorkspaceForm,
)
import environment.services as services
import environment.serializers as serializers
from environment.decorators import cloud_identity_required, require_DELETE

User = get_user_model()


ProjectedWorkbenchCost = namedtuple("ProjectedWorkbenchCost", "resource cost")


@require_GET
@login_required
@cloud_identity_required
def get_workspaces_list(request):
    user = User.objects.get(id=request.GET.get("user_id"))
    workspaces = services.get_workspaces_list(user)
    return JsonResponse(
        {"code": 200, "workspaces": serializers.serialize_workspaces(workspaces)}
    )


@require_GET
@login_required
@cloud_identity_required
def get_shared_workspaces_list(request):
    user = User.objects.get(id=request.GET.get("user_id"))
    shared_workspaces = services.get_shared_workspaces_list(user)
    return JsonResponse(
        {
            "code": 200,
            "shared_workspaces": serializers.serialize_shared_workspaces(
                shared_workspaces
            ),
        }
    )


@require_GET
@login_required
@cloud_identity_required
def get_billing_accounts_list(request):
    user = User.objects.get(id=request.GET.get("user_id"))
    billing_accounts = services.get_billing_accounts_list(user)
    return JsonResponse({"code": 200, "billing_accounts": billing_accounts})


@require_GET
@login_required
def get_user(request):
    return JsonResponse({"code": 200, "user": serializers.serialize_user(request.user)})


@require_POST
@login_required
@cloud_identity_required
def create_workspace(request):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    billing_accounts_list = services.get_billing_accounts_list(user)
    form = CreateWorkspaceForm(
        data, billing_accounts_list=billing_accounts_list
    )
    if form.is_valid():
        services.create_workspace(
            user=request.user,
            billing_account_id=form.cleaned_data["billing_account_id"],
            region=form.cleaned_data["region"],
        )
        return HttpResponse(status=202)
    else:
        return HttpResponse(status=400)


@require_DELETE
@login_required
@cloud_identity_required
def delete_workspace(request):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    services.delete_workspace(
        user=user,
        gcp_project_id=data.get("gcp_project_id"),
        billing_account_id=data.get("billing_account_id"),
        region=data.get("region"),
    )
    return HttpResponse(status=202)


@require_POST
@login_required
@cloud_identity_required
def create_shared_workspace(request):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    billing_accounts_list = services.get_billing_accounts_list(user)
    form = CreateSharedWorkspaceForm(
        data, billing_accounts_list=billing_accounts_list
    )
    if form.is_valid():
        services.create_shared_workspace(
            user=request.user,
            billing_account_id=form.cleaned_data["billing_account_id"],
        )
        return HttpResponse(status=202)
    else:
        return HttpResponse(status=400)


@require_DELETE
@login_required
@cloud_identity_required
def delete_shared_workspace(request):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    services.delete_shared_workspace(
        user=user,
        gcp_project_id=data.get("gcp_project_id"),
        billing_account_id=data.get("billing_account_id"),
    )
    return HttpResponse(status=202)
