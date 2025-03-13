import concurrent
import json
import re
from collections import namedtuple

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods
from django.contrib.auth import get_user_model

import environment.constants as constants
import environment.services as services
import environment.serializers as serializers
from environment.decorators import (
    cloud_identity_required,
    require_DELETE,
    require_PATCH,
    billing_account_required,
    console_permission_required,
)
from environment.entities import WorkflowStatus, WorkspaceStatus, Region, WorkflowType
from environment.exceptions import (
    CreateCloudGroupFailed,
    ChangeEnvironmentInstanceTypeFailed,
)

from environment.forms import (
    CloudIdentityPasswordForm,
    CreateResearchEnvironmentForm,
    CreateWorkspaceForm,
    ShareBillingAccountForm,
    CreateSharedWorkspaceForm,
    CreateSharedBucketForm,
    BucketSharingForm,
    AddUserToCloudGroupForm,
    AddCloudGroupForm,
    RemoveUserFromCloudGroupForm,
    AddRolesToCloudGroupForm,
    RemoveRolesFromCloudGroupForm,
    UpdateWorkspaceBillingAccountForm,
)
from environment.models import (
    BillingAccountSharingInvite,
    Workflow,
    BucketSharingInvite,
    VMInstance,
    CloudGroup,
    CloudIdentity,
)
from environment.utilities import user_has_cloud_identity

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
