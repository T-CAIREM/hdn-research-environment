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
