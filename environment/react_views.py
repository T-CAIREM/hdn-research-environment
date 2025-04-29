from collections import namedtuple


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth import get_user_model

import environment.services as services
import environment.serializers as serializers
from environment.decorators import (
    cloud_identity_required,
)

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
