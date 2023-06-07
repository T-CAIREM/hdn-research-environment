import json
import concurrent

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.views.decorators.http import require_http_methods, require_GET
from google.cloud.workflows.executions_v1beta.types.executions import Execution

import environment.services as services
import environment.constants as constants
from environment.forms import (
    CreateResearchEnvironmentForm,
    CloudIdentityPasswordForm,
    CreateWorkspaceForm,
    ShareBillingAccountForm,
)
from environment.decorators import (
    cloud_identity_required,
    require_DELETE,
    require_PATCH,
)
from environment.entities import Region, InstanceType
from environment.utilities import (
    user_has_cloud_identity,
)
from environment.models import Workflow, BillingAccountSharingInvite


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
        environment_project_workflow_future = executor.submit(
            services.get_environments_with_projects, request.user
        )
        workspace_creation_workflows_future = executor.submit(
            services.get_workspace_creation_workflows, request.user
        )

    workspaces_list = workspaces_list_future.result()
    environment_project_workflow_triplets = environment_project_workflow_future.result()
    billing_accounts_list = billing_accounts_list_future.result()
    workspace_creation_workflows = workspace_creation_workflows_future.result()

    environments = map(lambda pair: pair[0], environment_project_workflow_triplets)
    available_project_environment_workflow_triplets = (
        services.get_available_projects_with_environments(
            request.user,
            environments,
        )
    )
    projects_with_environments_being_created = (
        services.get_projects_with_environment_being_created(
            available_project_environment_workflow_triplets
        )
    )
    environment_projects_pairs_with_creating = (
        projects_with_environments_being_created + environment_project_workflow_triplets
    )

    sorted_environments_project_workflow_triplets_dict = (
        services.sort_environments_per_workspace(
            environment_projects_pairs_with_creating,
            workspaces_list,
            billing_accounts_list,
        )
    )

    context = {
        "available_project_environment_workflow_triplets": available_project_environment_workflow_triplets,
        "environment_project_workflow_triplets": environment_projects_pairs_with_creating,
        "workspace_project_environment_workflow_triplets_dict": sorted_environments_project_workflow_triplets_dict,
        "workspace_creation_workflows": workspace_creation_workflows,
        "billing_accounts_list": billing_accounts_list,
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
        environment_project_workflow_future = executor.submit(
            services.get_environments_with_projects, request.user
        )

    workspaces_list = workspaces_list_future.result()
    environment_project_workflow_triplets = environment_project_workflow_future.result()

    environments = map(lambda pair: pair[0], environment_project_workflow_triplets)
    available_project_environment_workflow_triplets = (
        services.get_available_projects_with_environments(
            request.user,
            environments,
        )
    )
    projects_with_environments_being_created = (
        services.get_projects_with_environment_being_created(
            available_project_environment_workflow_triplets
        )
    )
    environment_projects_pairs_with_creating = (
        projects_with_environments_being_created + environment_project_workflow_triplets
    )

    sorted_environments_project_workflow_triplets_dict = (
        services.sort_environments_per_workspace(
            environment_projects_pairs_with_creating, workspaces_list
        )
    )

    context = {
        "environment_project_workflow_triplets": environment_project_workflow_triplets,
        "workspace_project_environment_workflow_triplets_dict": sorted_environments_project_workflow_triplets_dict,
    }

    execution_resource_name = request.GET.get("execution_resource_name")
    if execution_resource_name:
        workflow = Workflow.objects.get(execution_resource_name=execution_resource_name)
        workflow_state_context = {
            "recent_workflow": workflow,
            "recent_workflow_failed": workflow.status == Workflow.FAILED,
            "recent_workflow_succeeded": workflow.status == Workflow.SUCCESS,
        }
        context = {**context, **workflow_state_context}

    return render(
        request,
        "environment/_available_environments_list.html",
        context,
    )


@require_http_methods(["GET", "POST"])
@login_required
@cloud_identity_required
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
def create_research_environment(request, project_slug, project_version):
    workspaces_list = services.get_workspaces_list(request.user)
    project = services.get_available_projects(request.user).get(
        slug=project_slug, version=project_version
    )

    if request.method == "POST":
        form = CreateResearchEnvironmentForm(
            request.POST, workspace_list=workspaces_list
        )
        if form.is_valid():
            cpu_usage = services.cpu_usage(
                value=InstanceType(form.cleaned_data["instance_type"]).cpus(),
                user=request.user,
            )
            if cpu_usage <= constants.MAX_CPU_USAGE:
                services.create_research_environment(
                    user=request.user,
                    project=project,
                    workspace_name=form.cleaned_data["workspace_id"],
                    instance_type=form.cleaned_data["instance_type"],
                    environment_type=form.cleaned_data["environment_type"],
                    persistent_disk=form.cleaned_data.get("persistent_disk"),
                    gpu_accelerator=form.cleaned_data.get("gpu_accelerator"),
                )
                return redirect("research_environments")
            else:
                messages.error(
                    request,
                    f"Quota exceeded - the specified configuration would use {cpu_usage} out of {constants.MAX_CPU_USAGE} CPUs",
                )
    else:
        form = CreateResearchEnvironmentForm(workspace_list=workspaces_list)

    context = {
        "form": form,
        "project": project,
        "exceeded_quotas": [],
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
    else:
        token = request.GET.get("token")
        if token:
            invite = BillingAccountSharingInvite.objects.select_related("owner").get(
                token=token, is_revoked=False
            )
            context = {"token": token, "invitation_owner": invite.owner}
            return render(
                request, "environment/manage_shared_billing_invitation.html", context
            )

    return redirect("research_environments")


@require_PATCH
@login_required
@cloud_identity_required
def stop_running_environment(request):
    data = json.loads(request.body)
    services.stop_running_environment(
        user=request.user,
        project_id=data["project_id"],
        workbench_id=data["workbench_id"],
        region=Region(data["region"]),
        gcp_project_id=data["gcp_project_id"],
    )
    return JsonResponse({})


@require_PATCH
@login_required
@cloud_identity_required
def start_stopped_environment(request):
    data = json.loads(request.body)
    services.start_stopped_environment(
        user=request.user,
        project_id=data["project_id"],
        workbench_id=data["workbench_id"],
        region=Region(data["region"]),
        gcp_project_id=data["gcp_project_id"],
    )
    return JsonResponse({})


@require_PATCH
@login_required
@cloud_identity_required
def change_environment_instance_type(request):
    data = json.loads(request.body)
    services.change_environment_instance_type(
        user=request.user,
        project_id=data["project_id"],
        workbench_id=data["workbench_id"],
        region=Region(data["region"]),
        new_instance_type=InstanceType(data["instance_type"]),
        gcp_project_id=data["gcp_project_id"],
    )
    return JsonResponse({})


@require_DELETE
@login_required
@cloud_identity_required
def delete_environment(request):
    data = json.loads(request.body)
    services.delete_environment(
        user=request.user,
        project_id=data["project_id"],
        workbench_id=data["workbench_id"],
        region=Region(data["region"]),
        gcp_project_id=data["gcp_project_id"],
    )
    return JsonResponse({})


@require_GET
@login_required
@cloud_identity_required
def check_execution_status(request):
    execution_resource_name = request.GET["execution_resource_name"]
    execution_state = services.get_execution_state(
        execution_resource_name=execution_resource_name
    )
    finished = execution_state != Execution.State.ACTIVE
    if finished:
        services.mark_workflow_as_finished(
            execution_resource_name=execution_resource_name,
            execution_state=execution_state,
        )
    return JsonResponse({"finished": finished})
