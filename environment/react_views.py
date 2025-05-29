import concurrent
from collections import namedtuple

from environment.entities import WorkspaceStatus
from environment.models import VMInstance, GPUAccelerator
import json


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth import get_user_model
from environment.forms import (
    CreateWorkspaceForm,
    CreateSharedWorkspaceForm,
    CreateResearchEnvironmentForm,
)
from django.apps import apps
import environment.services as services
import environment.serializers as serializers
from environment.decorators import cloud_identity_required, require_DELETE

User = get_user_model()
PublishedProject = apps.get_model("project", "PublishedProject")


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
    form = CreateWorkspaceForm(data, billing_accounts_list=billing_accounts_list)
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
    form = CreateSharedWorkspaceForm(data, billing_accounts_list=billing_accounts_list)
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


@require_GET
def get_environment_resource_options():
    serialized_available_instances = serializers.serialize_vm_instances(
        VMInstance.objects.all()
    )
    serialized_available_gpu_accelerators = serializers.serialize_gpu_accelerators(
        GPUAccelerator.objects.all()
    )
    return JsonResponse(
        {
            "instances": serialized_available_instances,
            "accelerators": serialized_available_gpu_accelerators,
        }
    )


@require_GET
@login_required
def get_available_projects(request):
    user = User.objects.get(id=request.GET.get("user_id"))
    projects = services.get_available_projects(user)
    return JsonResponse({"projects": serializers.serialize_projects(projects)})


@require_POST
@login_required
@cloud_identity_required
def create_research_environment(request, workspace_project_id):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))

    with concurrent.futures.ThreadPoolExecutor() as executor:
        workspace_get_feature = executor.submit(
            services.get_simplified_workspace, workspace_project_id, request.user
        )
        get_shared_bucket_feature = executor.submit(
            services.get_shared_bucket, data.bucket_name, request.user
        )
    workspace = workspace_get_feature.result()
    shared_bucket = get_shared_bucket_feature.result()

    if not workspace.status == WorkspaceStatus.CREATED:
        return HttpResponse("Workspace is not available", status=406)
    project = PublishedProject.objects.get(data.project_id)

    form = CreateResearchEnvironmentForm(
        data,
        selected_workspace=workspace,
        projects_list=[project],
        buckets_list=[shared_bucket],
    )
    if form.is_valid():
        project = services.get_project(form.cleaned_data["project_id"])
        services.create_research_environment(
            user=user,
            project=project,
            workspace_project_id=form.cleaned_data["workspace_project_id"],
            machine_type=form.cleaned_data["machine_type"],
            workbench_type=form.cleaned_data["environment_type"],
            disk_size=form.cleaned_data.get("disk_size"),
            gpu_accelerator_type=form.cleaned_data.get("gpu_accelerator"),
            sharing_bucket_identifiers=form.cleaned_data.get("shared_bucket"),
        )
        return HttpResponse(status=202)
    else:
        return HttpResponse(status=400)
