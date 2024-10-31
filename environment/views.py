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
from environment.decorators import (
    cloud_identity_required,
    require_DELETE,
    require_PATCH,
    billing_account_required,
    console_permission_required,
)
from environment.entities import WorkflowStatus, WorkspaceStatus, Region, WorkflowType
from environment.exceptions import CreateCloudGroupFailed
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


@require_http_methods(["GET", "POST"])
@login_required
def identity_provisioning(request):
    if user_has_cloud_identity(request.user):
        return redirect("research_environments")

    # TODO: Handle the case where the user was created successfully, but the response was lost.
    if request.method == "POST":
        form = CloudIdentityPasswordForm(request.POST)
        if form.is_valid():
            services.create_cloud_identity(
                request.user,
                form.cleaned_data.get("password"),
                form.cleaned_data.get("recovery_email"),
            )
            return redirect("research_environments")
    else:
        form = CloudIdentityPasswordForm()

    return render(
        request, "environment/identity_provisioning.html", context={"form": form}
    )


@require_GET
@login_required
@cloud_identity_required
def research_environments(request):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        workspaces_list_future = executor.submit(
            services.get_workspaces_list, request.user
        )
        billing_accounts_list_future = executor.submit(
            services.get_billing_accounts_list, request.user
        )
        shared_workspaces_list_feature = executor.submit(
            services.get_shared_workspaces_list, request.user
        )

    workspaces = workspaces_list_future.result()
    billing_accounts_list = billing_accounts_list_future.result()
    shared_workspaces = shared_workspaces_list_feature.result()
    running_workflows = services.get_running_workflows(request.user)
    billing_account_id_to_name_map = {
        acc["id"]: acc["name"] for acc in billing_accounts_list
    }

    context = {
        "shared_workspaces": shared_workspaces,
        "workspaces_with_workbenches": workspaces,
        "billing_accounts_list": billing_accounts_list,
        "billing_account_id_to_name_map": billing_account_id_to_name_map,
        "workflows": running_workflows,
        "websocket_url": settings.CLOUD_RESEARCH_ENVIRONMENTS_API_URL,
    }

    return render(
        request,
        "environment/research_environments.html",
        context,
    )


@require_GET
@login_required
@cloud_identity_required
def research_environments_partial(request):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        workspaces_list_future = executor.submit(
            services.get_workspaces_list, request.user
        )
        billing_accounts_list_future = executor.submit(
            services.get_billing_accounts_list, request.user
        )
        shared_workspaces_list_feature = executor.submit(
            services.get_shared_workspaces_list, request.user
        )

    workspaces = workspaces_list_future.result()
    billing_accounts_list = billing_accounts_list_future.result()
    shared_workspaces = shared_workspaces_list_feature.result()
    running_workflows = services.get_running_workflows(request.user)
    billing_account_id_to_name_map = {
        acc["id"]: acc["name"] for acc in billing_accounts_list
    }

    context = {
        "shared_workspaces": shared_workspaces,
        "workspaces_with_workbenches": workspaces,
        "billing_accounts_list": billing_accounts_list,
        "workflows": running_workflows,
        "websocket_url": settings.CLOUD_RESEARCH_ENVIRONMENTS_API_URL,
        "billing_account_id_to_name_map": billing_account_id_to_name_map,
    }

    execution_resource_name = request.GET.get("execution_resource_name")
    if execution_resource_name:
        workflow = services.get_execution(execution_resource_name)
        success = workflow.status == WorkflowStatus.SUCCESS
        workflow_state_context = {
            "recent_workflow": workflow,
            "recent_workflow_failed": workflow.status == WorkflowStatus.FAILURE,
            "recent_workflow_succeeded": success,
            "workflow_finished_message": workflow.error_information,
        }

        # remove workspace from active workspaces if it was just deleted successfully
        if success and workflow.type == WorkflowType.WORKSPACE_DELETION:
            context["workspaces_with_workbenches"] = [
                workspace
                for workspace in context["workspaces_with_workbenches"]
                if workspace.gcp_project_id != workflow.workspace_id
            ]

        if success and workflow.type == WorkflowType.SHARED_WORKSPACE_DELETION:
            context["shared_workspaces"] = [
                workspace
                for workspace in context["shared_workspaces"]
                if workspace.gcp_project_id != workflow.workspace_id
            ]

        context = {**context, **workflow_state_context}

    return render(
        request,
        "environment/_environment_tabs.html",
        context,
    )


@require_http_methods(["GET", "POST"])
@login_required
@cloud_identity_required
@billing_account_required
def create_workspace(request):
    billing_accounts_list = services.get_billing_accounts_list(request.user)

    if request.method == "POST":
        form = CreateWorkspaceForm(
            request.POST, billing_accounts_list=billing_accounts_list
        )
        if form.is_valid():
            services.create_workspace(
                user=request.user,
                billing_account_id=form.cleaned_data["billing_account_id"],
                region=form.cleaned_data["region"],
            )
            return redirect("research_environments")
    else:
        form = CreateWorkspaceForm(billing_accounts_list=billing_accounts_list)

    exceeded_quotas = services.exceeded_quotas(request.user)
    context = {
        "form": form,
        "exceeded_quotas": exceeded_quotas,
    }
    return render(request, "environment/create_workspace.html", context)


@require_http_methods(["GET", "POST"])
@login_required
@cloud_identity_required
@billing_account_required
def create_shared_workspace(request):
    billing_accounts_list = services.get_billing_accounts_list(request.user)

    if request.method == "POST":
        form = CreateSharedWorkspaceForm(
            request.POST, billing_accounts_list=billing_accounts_list
        )
        if form.is_valid():
            services.create_shared_workspace(
                user=request.user,
                billing_account_id=form.cleaned_data["billing_account_id"],
            )
            return redirect("research_environments")
    else:
        form = CreateSharedWorkspaceForm(billing_accounts_list=billing_accounts_list)

    context = {
        "form": form,
    }
    return render(request, "environment/create_shared_workspace.html", context)


@require_http_methods(["GET", "POST"])
@login_required
@cloud_identity_required
def create_research_environment(request, workspace_id):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        workspaces_list_future = executor.submit(
            services.get_workspaces_list, request.user
        )
        shared_workspaces_list_feature = executor.submit(
            services.get_shared_workspaces_list, request.user
        )
    workspaces_list = workspaces_list_future.result()
    shared_workspaces = shared_workspaces_list_feature.result()
    shared_buckets = services.get_shared_buckets(shared_workspaces)

    available_workspaces = list(
        workspace
        for workspace in workspaces_list
        if workspace.status == WorkspaceStatus.CREATED
    )
    if not available_workspaces:
        messages.info(
            request,
            "You have to have at least one workspace in order to create a research environment. You can create one using the form below.",
        )
        return redirect("create_workspace")
    selected_workspace = next(
        workspace
        for workspace in available_workspaces
        if workspace.gcp_project_id == workspace_id
    )
    projects = services.get_available_projects(request.user)

    if request.method == "POST":
        form = CreateResearchEnvironmentForm(
            request.POST,
            selected_workspace=selected_workspace,
            projects_list=projects,
            buckets_list=shared_buckets,
        )
        if form.is_valid():
            selected_workbench = form.cleaned_data["machine_type"]
            workbench_cpu_usage = selected_workbench.cpu
            new_cpu_usage = (
                services.cpu_usage(available_workspaces) + workbench_cpu_usage
            )
            if new_cpu_usage <= constants.MAX_CPU_USAGE:
                project = services.get_project(form.cleaned_data["project_id"])
                services.create_research_environment(
                    user=request.user,
                    project=project,
                    workspace_project_id=form.cleaned_data["workspace_project_id"],
                    machine_type=form.cleaned_data["machine_type"],
                    workbench_type=form.cleaned_data["environment_type"],
                    disk_size=form.cleaned_data.get("disk_size"),
                    gpu_accelerator_type=form.cleaned_data.get("gpu_accelerator"),
                    sharing_bucket_identifiers=form.cleaned_data.get("shared_bucket"),
                )
                messages.info(
                    request,
                    "Workbench creation has been started - it takes between 3 and 10 minutes based on the selected configuration.",
                )
                return redirect("research_environments")
            else:
                messages.error(
                    request,
                    f"Quota exceeded - the specified configuration would use {new_cpu_usage} out of {constants.MAX_CPU_USAGE} CPUs",
                )
    else:
        form = CreateResearchEnvironmentForm(
            selected_workspace=selected_workspace,
            projects_list=projects,
            buckets_list=shared_buckets,
        )

    instance_projected_cost = {}
    region = Region(selected_workspace.region)
    instances = VMInstance.objects.filter(region__region=region.value)
    projected_costs = [
        ProjectedWorkbenchCost(instance.id, instance.price) for instance in instances
    ]
    instance_projected_cost[region] = projected_costs

    context = {
        "selected_workspace": selected_workspace,
        "form": form,
        "instance_projected_costs": instance_projected_cost,
        "gpu_projected_costs": constants.GPU_PROJECTED_COSTS,
        "data_storage_projected_costs": constants.DATA_STORAGE_PROJECTED_COSTS,
    }
    return render(request, "environment/create_research_environment.html", context)


@require_http_methods(["GET", "POST"])
@login_required
@cloud_identity_required
def create_shared_bucket(request, workspace_id):
    shared_workspaces_list = services.get_shared_workspaces_list(request.user)
    available_shared_workspaces = [
        workspace
        for workspace in shared_workspaces_list
        if workspace.status == WorkspaceStatus.CREATED
    ]
    if not available_shared_workspaces:
        messages.info(
            request,
            "You have to have at least one shared workspace in order to create a shared_bucket. You can create one using the form below.",
        )
        return redirect("create_workspace")
    selected_shared_workspace = next(
        shared_workspace
        for shared_workspace in available_shared_workspaces
        if shared_workspace.gcp_project_id == workspace_id
    )

    if request.method == "POST":
        form = CreateSharedBucketForm(
            request.POST, selected_shared_workspace=selected_shared_workspace
        )
        if form.is_valid():
            services.create_shared_buket(
                user=request.user,
                region=form.cleaned_data["region"],
                user_defined_bucket_name=form.cleaned_data["user_defined_bucket_name"],
                workspace_project_id=form.cleaned_data["workspace_project_id"],
            )
            return redirect("research_environments")
    else:
        form = CreateSharedBucketForm(
            selected_shared_workspace=selected_shared_workspace
        )

    context = {
        "selected_shared_workspace": selected_shared_workspace,
        "form": form,
    }
    return render(request, "environment/create_shared_bucket.html", context)


@require_http_methods(["GET", "POST"])
@login_required
@cloud_identity_required
@transaction.atomic
def manage_billing_account(request, billing_account_id):
    if not services.is_billing_account_owner(request.user, billing_account_id):
        raise Http404()

    owner = request.user
    billing_account_sharing_form = ShareBillingAccountForm()

    if request.method == "POST":
        form_action = request.POST["action"]
        if form_action == "share_account":
            billing_account_sharing_form = ShareBillingAccountForm(request.POST)
            if billing_account_sharing_form.is_valid():
                services.invite_user_to_shared_billing_account(
                    request=request,
                    owner=owner,
                    user_email=billing_account_sharing_form.cleaned_data["user_email"],
                    billing_account_id=billing_account_id,
                )
                return redirect(request.path)
        elif form_action == "revoke_access":
            services.revoke_billing_account_access(request.POST["share_id"])
            return redirect(request.path)

    billing_account_shares = services.get_owned_shares_of_billing_account(
        owner=owner, billing_account_id=billing_account_id
    )
    pending_shares = [
        share for share in billing_account_shares if not share.is_consumed
    ]
    consumed_shares = [share for share in billing_account_shares if share.is_consumed]

    context = {
        "billing_account_sharing_form": billing_account_sharing_form,
        "billing_account_id": billing_account_id,
        "pending_shares": pending_shares,
        "consumed_shares": consumed_shares,
    }

    return render(request, "environment/manage_billing_account.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def confirm_billing_account_sharing(request):
    if request.method == "POST":
        token = request.POST["token"]
        services.consume_billing_account_sharing_token(user=request.user, token=token)
        messages.info(
            request,
            "You accepted the billing invitation! The account will be accessible in a few moments.",
        )
        return redirect("research_environments")

    token = request.GET.get("token")
    if not token:
        messages.error(request, "The invitation is either invalid or expired.")
        return redirect("research_environments")

    invite = BillingAccountSharingInvite.objects.select_related("owner").get(
        token=token, is_revoked=False
    )
    context = {
        "token": token,
        "invitation_owner": invite.owner,
        "is_owner": request.user == invite.owner,
    }
    return render(request, "environment/manage_shared_billing_invitation.html", context)


@require_http_methods(["GET", "POST"])
@login_required
@cloud_identity_required
@transaction.atomic
def manage_shared_bucket(request, shared_workspace_name, shared_bucket_name):
    shared_workspaces_list = services.get_shared_workspaces_list(request.user)
    if not services.is_shared_bucket_owner(shared_workspaces_list, shared_bucket_name):
        raise Http404()

    bucket_content = services.get_shared_bucket_content(
        shared_bucket_name, request.user
    )

    owner = request.user
    bucket_sharing_form = BucketSharingForm(
        invitation_owner=owner, shared_bucket_name=shared_bucket_name
    )

    if request.method == "POST":
        form_action = request.POST["action"]
        if form_action == "share_account":
            bucket_sharing_form = BucketSharingForm(
                request.POST,
                invitation_owner=owner,
                shared_bucket_name=shared_bucket_name,
            )
            if bucket_sharing_form.is_valid():
                services.invite_user_to_shared_bucket(
                    request=request,
                    owner=owner,
                    user_email=bucket_sharing_form.cleaned_data["user_email"],
                    shared_bucket_name=shared_bucket_name,
                    shared_workspace_name=shared_workspace_name,
                    permissions=bucket_sharing_form.cleaned_data["user_permissions"],
                )
                return redirect(request.path)
        elif form_action == "revoke_access":
            services.revoke_shared_bucket_access(request.POST["share_id"])
            return redirect(request.path)

    bucket_shares = services.get_owned_shares_of_bucket(
        owner=owner, shared_bucket_name=shared_bucket_name
    )
    pending_shares = [share for share in bucket_shares if not share.is_consumed]
    consumed_shares = [share for share in bucket_shares if share.is_consumed]

    context = {
        "bucket_sharing_form": bucket_sharing_form,
        "shared_bucket_name": shared_bucket_name,
        "shared_workspace_name": shared_workspace_name,
        "pending_shares": pending_shares,
        "consumed_shares": consumed_shares,
        "bucket_content": bucket_content,
    }

    return render(request, "environment/manage_shared_bucket.html", context)


@require_http_methods(["GET"])
@login_required
@cloud_identity_required
@transaction.atomic
def manage_shared_bucket_files(request, shared_workspace_name, shared_bucket_name):
    shared_workspaces_list = services.get_shared_workspaces_list(request.user)
    if services.is_shared_bucket_owner(shared_workspaces_list, shared_bucket_name):
        return redirect(
            "manage_shared_bucket",
            shared_workspace_name=shared_workspace_name,
            shared_bucket_name=shared_bucket_name,
        )
    if not services.is_shared_bucket_admin(shared_workspaces_list, shared_bucket_name):
        raise Http404()

    bucket_content = services.get_shared_bucket_content(
        shared_bucket_name, request.user
    )

    context = {
        "shared_bucket_name": shared_bucket_name,
        "shared_workspace_name": shared_workspace_name,
        "bucket_content": bucket_content,
    }

    return render(request, "environment/manage_shared_bucket_files.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def confirm_bucket_sharing(request):
    if request.method == "POST":
        token = request.POST["token"]
        services.consume_bucket_sharing_token(user=request.user, token=token)
        messages.info(
            request,
            "You accepted the shared bucket invitation! The bucket will be accessible in a few moments.",
        )
        return redirect("research_environments")

    token = request.GET.get("token")
    if not token:
        messages.error(request, "The invitation is either invalid or expired.")
        return redirect("research_environments")

    invite = BucketSharingInvite.objects.select_related("owner").get(
        token=token, is_revoked=False
    )
    context = {
        "token": token,
        "invitation_owner": invite.owner,
        "is_owner": request.user == invite.owner,
    }
    return render(request, "environment/manage_shared_bucket_invitation.html", context)


@require_PATCH
@login_required
@cloud_identity_required
def stop_running_environment(request):
    data = json.loads(request.body)
    services.stop_running_environment(
        workbench_type=data["environment_type"],
        workbench_resource_id=data["instance_name"],
        user=request.user,
        workspace_project_id=data["gcp_project_id"],
    )
    return JsonResponse({})


@require_PATCH
@login_required
@cloud_identity_required
def start_stopped_environment(request):
    data = json.loads(request.body)
    services.start_stopped_environment(
        user=request.user,
        workbench_type=data["environment_type"],
        workbench_resource_id=data["instance_name"],
        workspace_project_id=data["gcp_project_id"],
    )
    return JsonResponse({})


@require_PATCH
@login_required
@cloud_identity_required
def change_environment_machine_type(request):
    data = json.loads(request.body)
    services.change_environment_machine_type(
        user=request.user,
        workspace_project_id=data["gcp_project_id"],
        machine_type=data["machine_type"],
        workbench_type=data["environment_type"],
        workbench_resource_id=data["instance_name"],
    )
    return JsonResponse({})


@require_DELETE
@login_required
@cloud_identity_required
def delete_environment(request):
    data = json.loads(request.body)
    services.delete_environment(
        user=request.user,
        workspace_project_id=data["gcp_project_id"],
        workbench_type=data["environment_type"],
        workbench_resource_id=data["instance_name"],
    )
    return JsonResponse({})


@require_DELETE
@login_required
@cloud_identity_required
def delete_workspace(request):
    data = json.loads(request.body)
    services.delete_workspace(
        user=request.user,
        gcp_project_id=data["gcp_project_id"],
        billing_account_id=data["billing_account_id"],
        region=data["region"],
    )
    return JsonResponse({})


@require_DELETE
@login_required
@cloud_identity_required
def delete_shared_workspace(request):
    data = json.loads(request.body)
    services.delete_shared_workspace(
        user=request.user,
        gcp_project_id=data["gcp_project_id"],
        billing_account_id=data["billing_account_id"],
    )
    return JsonResponse({})


@require_DELETE
@login_required
@cloud_identity_required
def delete_shared_bucket(request):
    data = json.loads(request.body)
    services.delete_shared_bucket(bucket_name=data["bucket_name"])
    return JsonResponse({})


@require_GET
@login_required
@cloud_identity_required
def check_execution_status(request):
    execution_resource_name = request.GET["execution_resource_name"]
    execution = services.get_execution(execution_resource_name=execution_resource_name)
    finished = execution.status != WorkflowStatus.IN_PROGRESS
    if finished:
        services.mark_workflow_as_finished(
            execution_resource_name=execution_resource_name,
        )
    return JsonResponse({"finished": finished})


@login_required
@cloud_identity_required
def generate_signed_url(request, bucket_name):
    filename = request.POST.get("filename")
    size = request.POST.get("size")

    signed_url = services.generate_signed_url(
        bucket_name=bucket_name,
        size=int(size),
        filename=filename,
        user=request.user,
    )

    return JsonResponse({"signed_url": signed_url})


@login_required
@cloud_identity_required
def get_shared_bucket_content(request, bucket_name):
    subdir = request.GET.get("subdir")
    bucket_content = services.get_shared_bucket_content(
        bucket_name=bucket_name, subdir=subdir, user=request.user
    )
    parent_subbed_dir = re.subn("/[^/]*/$", "/", subdir or "")
    context = {
        "shared_bucket_name": bucket_name,
        "bucket_content": bucket_content,
        "current_dir_path": subdir,
        "parent_dir": parent_subbed_dir[0] if parent_subbed_dir[1] else "",
    }
    return render(request, "environment/shared_bucket_files.html", context=context)


@login_required
@cloud_identity_required
def create_shared_bucket_directory(request, bucket_name):
    data = json.loads(request.body)
    services.create_shared_bucket_directory(
        bucket_name=bucket_name,
        parent_path=data["parent_path"],
        directory_name=data["directory_name"],
        user=request.user,
    )
    return JsonResponse({})


@require_DELETE
@login_required
@cloud_identity_required
def delete_shared_bucket_content(request, bucket_name):
    data = json.loads(request.body)
    services.delete_shared_bucket_content(
        bucket_name=bucket_name, full_path=data["full_path"], user=request.user
    )
    return JsonResponse({})


@require_http_methods(["GET"])
@login_required
@cloud_identity_required
def get_quotas(request, workspace_project_id, workspace_region):
    quotas_data_list = services.list_quotas_data(workspace_region, workspace_project_id)
    context = {"quotas": quotas_data_list, "workspace_project_id": workspace_project_id}

    return render(request, "environment/quotas_list.html", context, status=200)


@login_required
@cloud_identity_required
@console_permission_required("user.can_view_admin_console")
def add_user_to_cloud_group(request, user_id):
    user = User.objects.get(id=user_id)
    cloud_group_list = list(CloudGroup.objects.all())
    form = AddUserToCloudGroupForm(user=user, cloud_group_list=cloud_group_list)

    if request.method == "POST":
        form = AddUserToCloudGroupForm(
            request.POST, user=user, cloud_group_list=cloud_group_list
        )
        if form.is_valid():
            services.add_user_to_cloud_group(user, form.cleaned_data["cloud_group"])
            return redirect("cloud_groups")
    context = {"form": form, "user_id": user_id}
    return render(
        request, "environment/admin/add_user_to_cloud_groups.html", context=context
    )


@login_required
@cloud_identity_required
@console_permission_required("user.can_view_admin_console")
def remove_user_from_cloud_group(request, user_id):
    user = User.objects.get(id=user_id)
    form = RemoveUserFromCloudGroupForm(user=user)

    if request.method == "POST":
        form = RemoveUserFromCloudGroupForm(request.POST, user=user)
        if form.is_valid():
            services.remove_user_from_cloud_group(
                user, form.cleaned_data["cloud_group"]
            )
            return redirect("cloud_groups")
    context = {"form": form, "user_id": user_id}
    return render(
        request, "environment/admin/remove_user_from_cloud_groups.html", context=context
    )


@login_required
@cloud_identity_required
@console_permission_required("user.can_view_admin_console")
def create_cloud_group(request):
    form = AddCloudGroupForm()

    if request.method == "POST":
        form = AddCloudGroupForm(request.POST)
        if form.is_valid():
            try:
                services.create_cloud_group(
                    form.cleaned_data["name"], form.cleaned_data["description"]
                )
                return redirect("cloud_groups")
            except CreateCloudGroupFailed as error:
                context = {"form": form, "error_message": error}
                return render(
                    request,
                    "environment/admin/create_cloud_user_group.html",
                    context=context,
                )

    context = {"form": form}
    return render(
        request, "environment/admin/create_cloud_user_group.html", context=context
    )


@login_required
@cloud_identity_required
@console_permission_required("user.can_view_admin_console")
def delete_cloud_group(request):
    data = json.loads(request.body)
    services.delete_cloud_group(group_name=data["group_name"])
    return JsonResponse({})


@login_required
@cloud_identity_required
@console_permission_required("user.can_view_admin_console")
def cloud_groups(request):
    q = request.GET.get("q")
    cloud_identity_list = (
        CloudIdentity.objects.filter(user__username__icontains=q)
        if q
        else CloudIdentity.objects.all()
    )

    context = {"cloud_identity_list": cloud_identity_list}
    return render(
        request, "environment/admin/cloud_user_group_panel.html", context=context
    )


@login_required
@cloud_identity_required
@console_permission_required("user.can_view_admin_console")
def cloud_groups_management(request):
    q = request.GET.get("q")
    cloud_group_list = (
        CloudGroup.objects.prefetch_related("cloudidentity_set__user").filter(
            name__icontains=q
        )
        if q
        else CloudGroup.objects.prefetch_related("cloudidentity_set__user").all()
    )
    groups_with_roles = services.match_groups_with_roles(cloud_group_list)

    context = {"cloud_group_roles_dict": groups_with_roles}
    return render(
        request,
        "environment/admin/cloud_user_group_management_panel.html",
        context=context,
    )


@login_required
@cloud_identity_required
@console_permission_required("user.can_view_admin_console")
def cloud_groups_management_partial(request):
    q = request.GET.get("q")
    cloud_group_list = (
        CloudGroup.objects.prefetch_related("cloudidentity_set__user").filter(
            name__icontains=q
        )
        if q
        else CloudGroup.objects.prefetch_related("cloudidentity_set__user").all()
    )
    groups_with_roles = services.match_groups_with_roles(cloud_group_list)

    context = {"cloud_group_roles_dict": groups_with_roles}
    return render(
        request,
        "environment/admin/cloud_user_group_management_table.html",
        context=context,
    )


@login_required
@cloud_identity_required
@console_permission_required("user.can_view_admin_console")
def add_roles_to_cloud_group(request, cloud_group_id):
    cloud_group = CloudGroup.objects.get(id=cloud_group_id)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        cloud_list_future = executor.submit(services.list_cloud_group_roles)
        available_roles_list_future = executor.submit(
            services.get_cloud_group_iam_roles, cloud_group.name
        )

    cloud_roles = cloud_list_future.result()
    owned_cloud_roles = available_roles_list_future.result()
    available_roles = [
        role for role in cloud_roles if role.full_name not in owned_cloud_roles
    ]

    form = AddRolesToCloudGroupForm(
        cloud_group_name=cloud_group.name, available_roles=available_roles
    )

    if request.method == "POST":
        form = AddRolesToCloudGroupForm(
            request.POST,
            cloud_group_name=cloud_group.name,
            available_roles=available_roles,
        )
        if form.is_valid():
            services.add_roles_to_cloud_group(
                cloud_group.name, form.cleaned_data["roles_list"]
            )
            return redirect("cloud_groups_management")
    context = {"form": form, "cloud_group_id": cloud_group_id}
    return render(
        request, "environment/admin/add_roles_to_cloud_group.html", context=context
    )


@login_required
@cloud_identity_required
@console_permission_required("user.can_view_admin_console")
def remove_roles_from_cloud_group(request, cloud_group_id):
    cloud_group = CloudGroup.objects.get(id=cloud_group_id)

    available_roles = services.get_cloud_group_iam_roles(cloud_group.name)

    form = RemoveRolesFromCloudGroupForm(
        cloud_group_name=cloud_group.name, available_roles=available_roles
    )

    if request.method == "POST":
        form = RemoveRolesFromCloudGroupForm(
            request.POST,
            cloud_group_name=cloud_group.name,
            available_roles=available_roles,
        )
        if form.is_valid():
            services.remove_roles_from_cloud_group(
                cloud_group.name, form.cleaned_data["roles_list"]
            )
            return redirect("cloud_groups_management")
    context = {"form": form, "cloud_group_id": cloud_group_id}
    return render(
        request, "environment/admin/remove_roles_from_cloud_group.html", context=context
    )


@login_required
@cloud_identity_required
@console_permission_required("user.can_view_admin_console")
def get_datasets_monitoring_data(request):
    monitoring_data = services.get_datasets_monitoring_data()
    context = {"monitoring_data": monitoring_data}
    return render(
        request, "environment/admin/get_datasets_monitoring_data.html", context=context
    )


@login_required
@cloud_identity_required
@billing_account_required
def update_workspace_billing_account(
    request, workspace_project_id, current_billing_account_id
):
    billing_accounts_list = services.get_billing_accounts_list(request.user)

    if request.method == "POST":
        form = UpdateWorkspaceBillingAccountForm(
            request.POST,
            workspace_project_id=workspace_project_id,
            billing_accounts_list=billing_accounts_list,
        )
        if form.is_valid():
            services.update_workspace_billing_account(
                form.cleaned_data["workspace_project_id"],
                form.cleaned_data["billing_account_id"],
            )
            messages.success(
                request,
                f"Billing account updated for workspace {workspace_project_id}",
            )
            return redirect("research_environments")
    else:
        form = UpdateWorkspaceBillingAccountForm(
            workspace_project_id=workspace_project_id,
            billing_accounts_list=billing_accounts_list,
        )

    current_billing_account = [
        acc for acc in billing_accounts_list if acc["id"] == current_billing_account_id
    ][0]
    context = {
        "form": form,
        "workspace_project_id": workspace_project_id,
        "current_billing_account": current_billing_account,
    }
    return render(request, "environment/update_workspace_billing_account.html", context)


@require_GET
@login_required
@cloud_identity_required
def get_available_gpu_accelerators_partial(request):
    vm_instance_id = request.GET.get("vm_instance")
    gpu_accelerators = VMInstance.objects.get(id=vm_instance_id).gpu_accelerators.all()
    context = {"gpu_accelerators": gpu_accelerators}
    return render(request, "environment/gpu_accelerator_partial.html", context=context)
