import concurrent
from collections import namedtuple

from environment.entities import WorkspaceStatus
from environment.exceptions import ChangeEnvironmentInstanceTypeFailed
from environment.models import VMInstance, GPUAccelerator, BucketSharingInvite
from rest_framework.response import Response
import json
import re

from environment.utilities import user_has_cloud_identity
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth import get_user_model
from environment.forms import (
    CreateWorkspaceForm,
    CreateSharedWorkspaceForm,
    CreateResearchEnvironmentForm,
    CreateSharedBucketForm,
    BucketSharingForm,
    ShareBillingAccountForm,
    UpdateWorkspaceBillingAccountForm,
    CloudIdentityPasswordForm,
)
from django.apps import apps
import environment.services as services
import environment.serializers as serializers
from environment.decorators import (
    cloud_identity_required,
    require_DELETE,
    require_PATCH,
    billing_account_required,
)

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
def get_environment_resource_options(request):
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
            services.get_shared_bucket, data.get("shared_bucket"), request.user
        )
    workspace = workspace_get_feature.result()
    shared_bucket = get_shared_bucket_feature.result()

    if not workspace.status == WorkspaceStatus.CREATED:
        return HttpResponse("Workspace is not available", status=406)
    project = PublishedProject.objects.get(id=data["project_id"])

    form = CreateResearchEnvironmentForm(
        data,
        selected_workspace=workspace,
        projects_list=[project],
        buckets_list=[shared_bucket] if shared_bucket is not None else [],
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


@require_DELETE
@login_required
@cloud_identity_required
def delete_research_environment(request):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    services.delete_environment(
        user=user,
        workspace_project_id=data["gcp_project_id"],
        workbench_type=data["environment_type"],
        workbench_resource_id=data["instance_id"],
    )
    return HttpResponse(status=202)


@require_PATCH
@login_required
@cloud_identity_required
def stop_running_environment(request):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    services.stop_running_environment(
        workbench_type=data["environment_type"],
        workbench_resource_id=data["instance_id"],
        user=user,
        workspace_project_id=data["gcp_project_id"],
    )
    return HttpResponse(status=200)


@require_PATCH
@login_required
@cloud_identity_required
def start_stopped_environment(request):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    services.start_stopped_environment(
        user=user,
        workbench_type=data["environment_type"],
        workbench_resource_id=data["instance_id"],
        workspace_project_id=data["gcp_project_id"],
    )
    return HttpResponse(status=200)


@require_PATCH
@login_required
@cloud_identity_required
def change_environment_machine_type(request):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    try:
        services.change_environment_machine_type(
            user=user,
            workspace_project_id=data["gcp_project_id"],
            machine_type=data["machine_type"],
            workbench_type=data["environment_type"],
            workbench_resource_id=data["instance_name"],
        )
        return HttpResponse(status=202)
    except ChangeEnvironmentInstanceTypeFailed as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_POST
@login_required
@cloud_identity_required
def create_shared_bucket(request, workspace_id):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    shared_workspace = services.get_simplified_workspace(workspace_id, user)

    if not shared_workspace.status == WorkspaceStatus.CREATED:
        return HttpResponse("Workspace is not available", status=406)

    form = CreateSharedBucketForm(data, selected_shared_workspace=shared_workspace)
    if form.is_valid():
        services.create_shared_buket(
            user=user,
            region=form.cleaned_data["region"],
            user_defined_bucket_name=form.cleaned_data["user_defined_bucket_name"],
            workspace_project_id=form.cleaned_data["workspace_project_id"],
        )
        return HttpResponse(status=202)
    else:
        return HttpResponse(status=400)


@require_DELETE
@login_required
@cloud_identity_required
def delete_shared_bucket(request):
    data = json.loads(request.body)
    services.delete_shared_bucket(bucket_name=data["bucket_name"])
    return HttpResponse(status=200)


@require_POST
@login_required
@cloud_identity_required
def share_bucket(request, shared_workspace_name, shared_bucket_name):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    shared_workspaces = services.get_shared_workspaces_list(user)
    if not services.is_shared_bucket_owner(shared_workspaces, shared_bucket_name):
        raise Http404()

    bucket_sharing_form = BucketSharingForm(
        data,
        invitation_owner=user,
        shared_bucket_name=shared_bucket_name,
    )
    if bucket_sharing_form.is_valid():
        services.invite_user_to_shared_bucket(
            request=request,
            owner=user,
            user_email=bucket_sharing_form.cleaned_data["user_email"],
            shared_bucket_name=shared_bucket_name,
            shared_workspace_name=shared_workspace_name,
            permissions=bucket_sharing_form.cleaned_data["user_permissions"],
        )
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=400)


@require_GET
@login_required
@cloud_identity_required
def get_bucket_shares(request, shared_bucket_name):
    user = User.objects.get(id=request.GET.get("user_id"))
    bucket_shares = services.get_owned_shares_of_bucket(
        owner=user, shared_bucket_name=shared_bucket_name
    )
    return JsonResponse(
        {
            "bucket_sharing_invites": serializers.serialize_bucket_sharing_invitations(
                bucket_shares
            )
        },
        status=200,
    )


@require_POST
@login_required
@cloud_identity_required
def revoke_shared_bucket_access(request, shared_bucket_name):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    shared_workspaces = services.get_shared_workspaces_list(user)
    if not services.is_shared_bucket_owner(shared_workspaces, shared_bucket_name):
        raise Http404()
    services.revoke_shared_bucket_access(data["share_id"])

    return HttpResponse(status=200)


@require_POST
@login_required
def confirm_bucket_sharing(request):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    token = request.POST["token"]
    services.consume_bucket_sharing_token(user=user, token=token)
    return HttpResponse(status=200)


@require_GET
@login_required
def get_bucket_sharing_invitation(request):
    token = request.GET.get("token")
    if not token:
        return Response("The invitation is either invalid or expired.", status=400)

    invite = BucketSharingInvite.objects.select_related("owner").get(
        token=token, is_revoked=False
    )
    return JsonResponse(
        {
            "bucket_sharing_invite": serializers.serialize_bucket_sharing_invitations(
                invite
            )
        },
        status=200,
    )


@require_POST
@login_required
@cloud_identity_required
def share_billing_account(request, billing_account_id):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    if not services.is_billing_account_owner(user, billing_account_id):
        raise Http404()

    billing_account_sharing_form = ShareBillingAccountForm(data)
    if billing_account_sharing_form.is_valid():
        services.invite_user_to_shared_billing_account(
            request=request,
            owner=user,
            user_email=billing_account_sharing_form.cleaned_data["user_email"],
            billing_account_id=billing_account_id,
        )
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=400)


@require_GET
@login_required
@cloud_identity_required
def get_billing_shares(request, billing_account_id):
    user = User.objects.get(id=request.GET.get("user_id"))
    billing_shares = services.get_owned_shares_of_billing_account(
        owner=user, billing_account_id=billing_account_id
    )
    return JsonResponse(
        {
            "billing_sharing_invites": serializers.serialize_billing_sharing_invitations(
                billing_shares
            )
        },
        status=200,
    )


@require_POST
@login_required
@cloud_identity_required
def revoke_billing_account_access(request, billing_account_id):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    if not services.is_billing_account_owner(user, billing_account_id):
        raise Http404()
    services.revoke_billing_account_access(data["share_id"])

    return HttpResponse(status=200)


@require_POST
@login_required
def confirm_billing_account_sharing(request):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    token = request.POST["token"]
    services.consume_billing_account_sharing_token(user=user, token=token)
    return HttpResponse(status=200)


@require_POST
@login_required
@cloud_identity_required
def generate_signed_url(request, bucket_name):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))

    signed_url = services.generate_signed_url(
        bucket_name=bucket_name,
        size=int(data.get("size")),
        filename=data.get("filename"),
        user=user,
    )

    return JsonResponse({"signed_url": signed_url})


@require_GET
@login_required
@cloud_identity_required
def get_shared_bucket_content(request, bucket_name):
    subdir = request.GET.get("subdir")
    user = User.objects.get(id=request.GET.get("user_id"))
    bucket_content = services.get_shared_bucket_content(
        bucket_name=bucket_name, subdir=subdir, user=user
    )
    parent_subbed_dir = re.subn("/[^/]*/$", "/", subdir or "")
    context = {
        "shared_bucket_name": bucket_name,
        "bucket_content": serializers.serialize_shared_bucket_objects(bucket_content),
        "current_dir_path": subdir,
        "parent_dir": parent_subbed_dir[0] if parent_subbed_dir[1] else "",
    }
    return JsonResponse(context)


@require_POST
@login_required
@cloud_identity_required
def create_shared_bucket_directory(request, bucket_name):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    services.create_shared_bucket_directory(
        bucket_name=bucket_name,
        parent_path=data["parent_path"],
        directory_name=data["directory_name"],
        user=user,
    )
    return HttpResponse(status=200)


@require_DELETE
@login_required
@cloud_identity_required
def delete_shared_bucket_content(request, bucket_name):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    services.delete_shared_bucket_content(
        bucket_name=bucket_name, full_path=data["full_path"], user=user
    )
    return HttpResponse(status=200)


@require_POST
@login_required
@cloud_identity_required
@billing_account_required
def update_workspace_billing_account(request):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    billing_accounts_list = services.get_billing_accounts_list(user)

    form = UpdateWorkspaceBillingAccountForm(
        data,
        workspace_project_id=data["workspace_project_id"],
        billing_accounts_list=billing_accounts_list,
    )
    if form.is_valid():
        services.update_workspace_billing_account(
            form.cleaned_data["workspace_project_id"],
            form.cleaned_data["billing_account_id"],
        )
    return HttpResponse(status=200)


@require_GET
@login_required
@cloud_identity_required
def get_quotas(request, workspace_project_id, workspace_region):
    quotas_data_list = services.list_quotas_data(workspace_region, workspace_project_id)

    return JsonResponse({"quotas": serializers.serialize_quotas(quotas_data_list)})


@require_POST
@login_required
def identity_provisioning(request):
    data = json.loads(request.body)
    user = User.objects.get(id=data.get("user_id"))
    if user_has_cloud_identity(user):
        return HttpResponse(status=302)

    # TODO: Handle the case where the user was created successfully, but the response was lost.
    form = CloudIdentityPasswordForm(data)
    if form.is_valid():
        services.create_cloud_identity(
            request.user,
            form.cleaned_data.get("password"),
            form.cleaned_data.get("recovery_email"),
        )

    return HttpResponse(status=201)
