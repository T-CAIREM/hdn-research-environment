import concurrent
import json

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
)
from environment.entities import InstanceType, WorkflowStatus
from environment.forms import (
    CloudIdentityPasswordForm,
    CreateResearchEnvironmentForm,
    CreateWorkspaceForm,
    ShareBillingAccountForm,
)
from environment.models import BillingAccountSharingInvite, Workflow
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

    workspaces = workspaces_list_future.result()
    available_projects = services.get_available_projects(request.user)
    billing_accounts_list = billing_accounts_list_future.result()
    running_workflows = services.get_running_workflows(request.user)

    context = {
        "workspaces_with_workbenches": workspaces,
        "available_projects": available_projects,
        "billing_accounts_list": billing_accounts_list,
        "workflows": running_workflows,
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

    workspaces = workspaces_list_future.result()
    available_projects = services.get_available_projects(request.user)
    billing_accounts_list = billing_accounts_list_future.result()
    running_workflows = services.get_running_workflows(request.user)

    context = {
        "workspaces_with_workbenches": workspaces,
        "available_projects": available_projects,
        "billing_accounts_list": billing_accounts_list,
        "workflows": running_workflows,
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
def create_workspace(request):
    billing_accounts_list = services.get_billing_accounts_list(request.user)
    if not billing_accounts_list:
        messages.info(
            request,
            "You have to have access to at least one billing account in order to create a workspace. Visit the Billing tab for more information.",
        )
        return redirect("research_environments")

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
def create_research_environment(request, project_slug, project_version):
    workspaces_list = services.get_workspaces_list(request.user)
    if not workspaces_list:
        messages.info(
            request,
            "You have to have at least one workspace in order to create a research environment. You can create one using the form below.",
        )
        return redirect("create_workspace")

    project = services.get_available_projects(request.user).get(
        slug=project_slug, version=project_version
    )

    if request.method == "POST":
        form = CreateResearchEnvironmentForm(
            request.POST, workspace_list=workspaces_list
        )
        if form.is_valid():
            workbench_cpu_usage = InstanceType(form.cleaned_data["machine_type"]).cpus()
            new_cpu_usage = services.cpu_usage(workspaces_list) + workbench_cpu_usage
            if new_cpu_usage <= constants.MAX_CPU_USAGE:
                services.create_research_environment(
                    user=request.user,
                    project=project,
                    workspace_project_id=form.cleaned_data["workspace_project_id"],
                    machine_type=form.cleaned_data["machine_type"],
                    workbench_type=form.cleaned_data["environment_type"],
                    disk_size=form.cleaned_data.get("disk_size"),
                    gpu_accelerator_type=form.cleaned_data.get("gpu_accelerator"),
                )
                return redirect("research_environments")
            else:
                messages.error(
                    request,
                    f"Quota exceeded - the specified configuration would use {new_cpu_usage} out of {constants.MAX_CPU_USAGE} CPUs",
                )
    else:
        form = CreateResearchEnvironmentForm(workspace_list=workspaces_list)

    context = {
        "form": form,
        "project": project,
        "instance_projected_costs": constants.INSTANCE_PROJECTED_COSTS,
        "gpu_projected_costs": constants.GPU_PROJECTED_COSTS,
        "data_storage_projected_costs": constants.DATA_STORAGE_PROJECTED_COSTS,
    }
    return render(request, "environment/create_research_environment.html", context)


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
    context = {"token": token, "invitation_owner": invite.owner}
    return render(request, "environment/manage_shared_billing_invitation.html", context)


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
