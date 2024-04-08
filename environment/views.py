import concurrent
import json
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

import environment.constants as constants
import environment.services as services
from environment.decorators import (
    cloud_identity_required,
    require_DELETE,
    require_PATCH,
    billing_account_required,
)
from environment.entities import InstanceType, WorkflowStatus, WorkspaceStatus
from environment.forms import (
    CloudIdentityPasswordForm,
    CreateResearchEnvironmentForm,
    CreateWorkspaceForm,
    ShareBillingAccountForm,
    CreateSharedWorkspaceForm,
    CreateSharedBucketForm,
    BucketSharingForm,
)
from environment.models import (
    BillingAccountSharingInvite,
    Workflow,
    BucketSharingInvite,
)
from environment.utilities import user_has_cloud_identity


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

    context = {
        "shared_workspaces": shared_workspaces,
        "workspaces_with_workbenches": workspaces,
        "billing_accounts_list": billing_accounts_list,
        "workflows": running_workflows,
        "websocket_url": settings.CLOUD_RESEARCH_ENVIRONMENTS_API_URL
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

    context = {
        "shared_workspaces": shared_workspaces,
        "workspaces_with_workbenches": workspaces,
        "billing_accounts_list": billing_accounts_list,
        "workflows": running_workflows,
        "websocket_url": settings.CLOUD_RESEARCH_ENVIRONMENTS_API_URL
    }

    execution_resource_name = request.GET.get("execution_resource_name")
    if execution_resource_name:
        workflow = services.get_execution(execution_resource_name)
        workflow_state_context = {
            "recent_workflow": workflow,
            "recent_workflow_failed": workflow.status == WorkflowStatus.FAILURE,
            "recent_workflow_succeeded": workflow.status == WorkflowStatus.SUCCESS,
            "workflow_finished_message": workflow.error_information,
        }
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
            workbench_cpu_usage = InstanceType(form.cleaned_data["machine_type"]).cpus()
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

    context = {
        "selected_workspace": selected_workspace,
        "form": form,
        "instance_projected_costs": constants.INSTANCE_PROJECTED_COSTS,
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
                    permissions=bucket_sharing_form.cleaned_data["user_permissions"]
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
