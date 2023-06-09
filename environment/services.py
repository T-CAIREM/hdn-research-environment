from typing import Tuple, Iterable, Optional, Dict
from collections import defaultdict

from django.db.models import Model
from django.contrib.sites.shortcuts import get_current_site
from django.apps import apps
from google.cloud.workflows import executions_v1beta
from google.cloud.workflows.executions_v1beta.types import executions

import environment.constants as constants
import environment.mailers as mailers
import environment.api.v1 as api_v1
import environment.api.v2 as api_v2
from environment.models import CloudIdentity, Workflow, BillingAccountSharingInvite
from environment.exceptions import (
    IdentityProvisioningFailed,
    StopEnvironmentFailed,
    StartEnvironmentFailed,
    DeleteEnvironmentFailed,
    ChangeEnvironmentInstanceTypeFailed,
    BillingSharingFailed,
    BillingAccessRevokationFailed,
    EnvironmentCreationFailed,
    GetAvailableEnvironmentsFailed,
    GetWorkspaceDetailsFailed,
    GetBillingAccountsListFailed,
    GetWorkspacesListFailed,
    CreateWorkspaceFailed,
)
from environment.deserializers import (
    deserialize_research_environments,
    deserialize_workspace_details,
    deserialize_workspaces,
)
from environment.entities import (
    ResearchEnvironment,
    InstanceType,
    Region,
    ResearchWorkspace,
)
from environment.utilities import left_join_iterators, inner_join_iterators


PublishedProject = apps.get_model("project", "PublishedProject")


User = Model


DEFAULT_REGION = "us-central1"


def _project_data_group(project: PublishedProject) -> str:
    # HACK: Use the slug and version to calculate the dataset group.
    # The result has to match the patterns for:
    # - Service Account ID: must start with a lower case letter, followed by one or more lower case alphanumerical characters that can be separated by hyphens
    # - Role ID: can only include letters, numbers, full stops and underscores
    #
    # Potential collisions may happen:
    # { slug: some-project, version: 1.1.0 } => someproject110
    # { slug: some-project1, version: 1.0 }  => someproject110
    return "".join(c for c in project.slug + project.version if c.isalnum())


def _environment_data_group(environment: ResearchEnvironment) -> str:
    return environment.group_granting_data_access


def create_cloud_identity(
    user: User, password: str, recovery_email: str
) -> Tuple[str, CloudIdentity]:
    gcp_user_id = user.username
    response = api_v2.create_cloud_identity(
        gcp_user_id,
        user.profile.first_names,
        user.profile.last_name,
        password,
        recovery_email,
    )
    if not response.ok:
        error_message = response.json()["message"]
        raise IdentityProvisioningFailed(error_message)

    body = response.json()
    identity = CloudIdentity.objects.create(
        user=user,
        gcp_user_id=gcp_user_id,
        email=body["primary_email"],
    )
    return identity


def get_billing_accounts_list(user: User):
    response = api_v2.list_billing_accounts(user.cloud_identity.email)
    if not response.ok:
        error_message = None
        try:
            error_message = response.json()
        finally:
            raise GetBillingAccountsListFailed(error_message)

    return response.json()


def get_owned_shares_of_billing_account(owner: User, billing_account_id: str):
    return owner.owner_billingaccountsharinginvite_set.filter(
        billing_account_id=billing_account_id, is_revoked=False
    )


def invite_user_to_shared_billing_account(
    request, owner: User, user_email: str, billing_account_id: str
) -> BillingAccountSharingInvite:
    invite = BillingAccountSharingInvite.objects.create(
        owner=owner,
        billing_account_id=billing_account_id,
        user_contact_email=user_email,
    )
    site_domain = get_current_site(request).domain
    mailers.send_billing_sharing_confirmation(site_domain=site_domain, invite=invite)
    return invite


def consume_billing_account_sharing_token(
    user: User, token: str
) -> BillingAccountSharingInvite:
    invite = BillingAccountSharingInvite.objects.get(token=token, is_revoked=False)
    invite.user = user
    invite.save()

    return invite


def share_billing_account(owner_email: str, user_email: str, billing_account_id: str):
    response = api_v2.share_billing_account(
        owner_email=owner_email,
        user_email=user_email,
        billing_account_id=billing_account_id,
    )
    if not response.ok:
        error_message = response.json()
        raise BillingSharingFailed(error_message)


def revoke_billing_account_access(billing_account_sharing_invite_id: int):
    billing_account_sharing_invite = BillingAccountSharingInvite.objects.select_related(
        "owner__cloud_identity", "user__cloud_identity"
    ).get(pk=billing_account_sharing_invite_id)
    billing_account_sharing_invite.is_revoked = True
    billing_account_sharing_invite.save()

    if billing_account_sharing_invite.is_consumed:
        _revoke_consumed_billing_account_access(billing_account_sharing_invite)


def _revoke_consumed_billing_account_access(
    billing_account_sharing_invite: BillingAccountSharingInvite,
):
    owner_email = billing_account_sharing_invite.owner.cloud_identity.email
    user_email = billing_account_sharing_invite.user.cloud_identity.email
    billing_account_id = billing_account_sharing_invite.billing_account_id

    response = api_v2.revoke_billing_account_access(
        owner_email=owner_email,
        user_email=user_email,
        billing_account_id=billing_account_id,
    )
    if not response.ok:
        error_message = response.json()
        raise BillingAccessRevokationFailed(error_message)


def create_workspace(user: User, billing_account_id: str, region: str):
    response = api_v2.create_workspace(
        email=user.cloud_identity.email,
        billing_account_id=billing_account_id,
        region=region,
    )
    if not response.ok:
        error_message = response.json()["error"]
        raise CreateWorkspaceFailed(error_message)
    execution_resource_name = response.json()["execution-name"]
    persist_workflow(
        user=user,
        execution_resource_name=execution_resource_name,
        type=Workflow.WORKSPACE_CREATE,
    )


def _create_workbench_kwargs(
    user: User,
    project: PublishedProject,
    workspace_name: str,
    instance_type: str,
    environment_type: str,
    persistent_disk: int,
    gpu_accelerator: Optional[str] = None,
) -> dict:
    gcp_user_id = user.cloud_identity.gcp_user_id

    common = {
        "gcp_user_id": gcp_user_id,
        "gcp_project_id": workspace_name,
        "environment_type": environment_type,
        "instance_type": instance_type,
        "group_granting_data_access": _project_data_group(project),
        "persistent_disk": str(persistent_disk),
        "bucket_name": project.project_file_root(),
    }
    if environment_type == "jupyter":
        vm_image = (
            "common-cu110-notebooks"
            if gpu_accelerator
            else "r-4-2-cpu-experimental-notebooks"
        )
        jupyter_kwargs = {
            "vm_image": vm_image,
            "gpu_accelerator": gpu_accelerator,
        }
        return {**common, **jupyter_kwargs}
    else:
        return common


def create_research_environment(
    user: User,
    project: PublishedProject,
    workspace_name: str,
    instance_type: str,
    environment_type: str,
    persistent_disk: int,
    gpu_accelerator: Optional[str] = None,
) -> str:
    kwargs = _create_workbench_kwargs(
        user,
        project,
        workspace_name,
        instance_type,
        environment_type,
        persistent_disk,
        gpu_accelerator,
    )
    response = api_v1.create_workbench(**kwargs)
    if not response.ok:
        error_message = response.json()[
            "error"
        ]  # TODO: Check all uses of "error"/"message"
        raise EnvironmentCreationFailed(error_message)

    execution_resource_name = response.json()["execution-name"]
    persist_workflow(
        user=user,
        execution_resource_name=execution_resource_name,
        project_id=project.pk,
        type=Workflow.CREATE,
        workspace_name=workspace_name,
    )

    return response.json()


def get_workspace_details(user: User, region: Region) -> ResearchWorkspace:
    gcp_user_id = user.cloud_identity.gcp_user_id
    response = api_v1.get_workspace_details(
        gcp_user_id=gcp_user_id,
        region=region.value,
    )
    if not response.ok:
        error_message = response.json()["error"]
        raise GetWorkspaceDetailsFailed(error_message)

    research_workspace = deserialize_workspace_details(response.json())
    return research_workspace


def is_user_workspace_setup_done(user: User) -> bool:
    try:
        workspace = get_workspace_details(user, Region(DEFAULT_REGION))
        return workspace.setup_finished
    except GetWorkspaceDetailsFailed:
        return False


def mark_user_workspace_setup_as_done(user: User):
    cloud_identity = user.cloud_identity
    cloud_identity.initial_workspace_setup_done = True
    cloud_identity.save()


def get_available_projects(user: User) -> Iterable[PublishedProject]:
    return PublishedProject.objects.accessible_by(user).prefetch_related("workflows")


def _get_projects_for_environments(
    environments: Iterable[ResearchEnvironment],
) -> Iterable[PublishedProject]:
    group_granting_data_accesses = list(map(_environment_data_group, environments))
    # FIXME: Given the fact that the groups are generated automatically in a non-reversible way,
    # the only way to match the projects to their environments is to fetch all the records and
    # calculate the group name for each of them.
    return [
        project
        for project in PublishedProject.objects.all()
        if _project_data_group(project) in group_granting_data_accesses
    ]


def get_active_environments(user: User) -> Iterable[ResearchEnvironment]:
    gcp_user_id = user.cloud_identity.gcp_user_id
    response = api_v1.get_workspace_list(gcp_user_id)
    if not response.ok:
        error_message = response.json()["error"]
        raise GetAvailableEnvironmentsFailed(error_message)
    all_environments = deserialize_research_environments(response.json())
    return [environment for environment in all_environments if environment.is_active]


def get_environments_with_projects(
    user: User,
) -> Iterable[Tuple[ResearchEnvironment, PublishedProject, Iterable[Workflow]]]:
    active_environments = get_active_environments(user)
    projects = _get_projects_for_environments(active_environments)
    environment_project_pairs = inner_join_iterators(
        _environment_data_group, active_environments, _project_data_group, projects
    )
    return [
        (environment, project, project.workflows.in_progress().filter(user=user))
        for environment, project in environment_project_pairs
    ]


def get_available_projects_with_environments(
    user: User,
    environments: Iterable[ResearchEnvironment],
) -> Iterable[
    Tuple[PublishedProject, Optional[ResearchEnvironment], Iterable[Workflow]]
]:
    available_projects = get_available_projects(user)
    project_environment_pairs = left_join_iterators(
        _project_data_group,
        available_projects,
        _environment_data_group,
        environments,
    )
    return [
        (project, environment, project.workflows.in_progress().filter(user=user))
        for project, environment in project_environment_pairs
    ]


def get_projects_with_environment_being_created(
    project_environment_workflow_triplets: Iterable[
        Tuple[PublishedProject, Optional[ResearchEnvironment], Iterable[Workflow]]
    ],
) -> Iterable[Tuple[None, PublishedProject, Iterable[Workflow]]]:
    return [
        (environment, project, workflows)
        for project, environment, workflows in project_environment_workflow_triplets
        if environment is None and workflows.exists()
    ]


def get_workspace_creation_workflows(user: User) -> Iterable[Workflow]:
    return Workflow.objects.filter(
        user=user, type=Workflow.WORKSPACE_CREATE, status=Workflow.INPROGRESS
    )


def get_environment_project_pairs_with_expired_access(
    user: User,
) -> Iterable[Tuple[ResearchEnvironment, PublishedProject]]:
    all_environment_project_pairs = get_environments_with_projects(user)
    return [
        (environment, project)
        for environment, project in all_environment_project_pairs
        if not project.has_access(user)
    ]


def sort_environments_per_workspace(
    environment_project_workflow_triplets: Iterable[
        Tuple[ResearchEnvironment, PublishedProject, Iterable[Workflow]]
    ],
    workspaces: Iterable[ResearchWorkspace],
    billing_accounts_list: Iterable,
) -> Dict[
    constants.WorkspaceBillingInfo,
    Tuple[ResearchEnvironment, PublishedProject, Iterable[Workflow]],
]:
    billing_id_mapping = match_workspace_with_billing_id(
        workspaces, billing_accounts_list
    )
    sorted_environments_project_workflow_triplets = defaultdict(
        list,
        {workspace.gcp_project_id: [] for workspace in workspaces},
    )
    for environment, project, workflows in environment_project_workflow_triplets:
        if environment:
            sorted_environments_project_workflow_triplets[
                environment.workspace_name
            ].append((environment, project, workflows))
        else:
            sorted_environments_project_workflow_triplets[
                workflows.last().workspace_name
            ].append((environment, project, workflows))

    sorted_environments_project_workflow_triplets_with_billing_info = {
        constants.WorkspaceBillingInfo(
            workspace.gcp_project_id,
            billing_id_mapping[workspace.gcp_billing_id],
        ): sorted_environments_project_workflow_triplets[workspace.gcp_project_id]
        for workspace in workspaces
    }
    return sorted_environments_project_workflow_triplets_with_billing_info


def match_workspace_with_billing_id(
    workspaces: Iterable[ResearchWorkspace], billing_accounts_list: Iterable
):
    billing_id_mapping = {
        entry.gcp_billing_id: entry.gcp_billing_id for entry in workspaces
    }
    for billing_account in billing_accounts_list:
        if billing_account["id"] in billing_id_mapping:
            billing_id_mapping[billing_account["id"]] = billing_account["name"]
    return billing_id_mapping


def get_workspaces_list(user: User) -> Iterable[ResearchWorkspace]:
    gcp_user_id = user.cloud_identity.gcp_user_id
    response = api_v1.get_workspace_list(gcp_user_id)
    if not response.ok:
        error_message = response.json()["error"]
        raise GetWorkspacesListFailed(error_message)
    return deserialize_workspaces(response.json())


def stop_running_environment(
    user: User, project_id: str, workbench_id: str, region: Region, gcp_project_id: str
) -> str:
    gcp_user_id = user.cloud_identity.gcp_user_id
    response = api_v1.stop_workbench(
        gcp_user_id=gcp_user_id,
        workbench_id=workbench_id,
        region=region.value,
        gcp_project_id=gcp_project_id,
    )
    if not response.ok:
        error_message = response.json()["error"]
        raise StopEnvironmentFailed(error_message)

    execution_resource_name = response.json()["execution-name"]
    persist_workflow(
        user=user,
        execution_resource_name=execution_resource_name,
        project_id=project_id,
        type=Workflow.PAUSE,
        workspace_name=gcp_project_id,
    )

    return response.json()


def start_stopped_environment(
    user: User, project_id: str, workbench_id: str, region: Region, gcp_project_id: str
) -> str:
    gcp_user_id = user.cloud_identity.gcp_user_id
    response = api_v1.start_workbench(
        gcp_user_id=gcp_user_id,
        workbench_id=workbench_id,
        region=region.value,
        gcp_project_id=gcp_project_id,
    )
    if not response.ok:
        error_message = response.json()["message"]
        raise StartEnvironmentFailed(error_message)

    execution_resource_name = response.json()["execution-name"]
    persist_workflow(
        user=user,
        execution_resource_name=execution_resource_name,
        project_id=project_id,
        type=Workflow.START,
        workspace_name=gcp_project_id,
    )

    return response.json()


def change_environment_instance_type(
    user: User,
    project_id: str,
    workbench_id: str,
    region: Region,
    gcp_project_id: str,
    new_instance_type: InstanceType,
) -> str:
    gcp_user_id = user.cloud_identity.gcp_user_id
    response = api_v1.change_workbench_instance_type(
        gcp_user_id=gcp_user_id,
        workbench_id=workbench_id,
        region=region.value,
        new_instance_type=new_instance_type.value,
        gcp_project_id=gcp_project_id,
    )
    if not response.ok:
        error_message = response.json()["message"]
        raise ChangeEnvironmentInstanceTypeFailed(error_message)

    execution_resource_name = response.json()["execution-name"]
    persist_workflow(
        user=user,
        execution_resource_name=execution_resource_name,
        project_id=project_id,
        type=Workflow.CHANGE,
        workspace_name=gcp_project_id,
    )

    return response.json()


def delete_environment(
    user: User, project_id: str, workbench_id: str, region: Region, gcp_project_id: str
) -> str:
    gcp_user_id = user.cloud_identity.gcp_user_id
    response = api_v1.delete_workbench(
        gcp_user_id=gcp_user_id,
        workbench_id=workbench_id,
        region=region.value,
        gcp_project_id=gcp_project_id,
    )
    if not response.ok:
        error_message = response.json()["message"]
        raise DeleteEnvironmentFailed(error_message)

    execution_resource_name = response.json()["execution-name"]
    persist_workflow(
        user=user,
        execution_resource_name=execution_resource_name,
        project_id=project_id,
        type=Workflow.DESTROY,
        workspace_name=gcp_project_id,
    )

    return response.json()


def persist_workflow(
    user: User,
    execution_resource_name: str,
    type: int,
    project_id: Optional[int] = None,
    workspace_name: Optional[str] = None,
) -> Workflow:
    return Workflow.objects.create(
        user=user,
        execution_resource_name=execution_resource_name,
        workspace_name=workspace_name,
        project_id=project_id,
        type=type,
        status=Workflow.INPROGRESS,
    )


def get_execution_state(execution_resource_name) -> executions.Execution.State:
    client = executions_v1beta.ExecutionsClient()
    execution = client.get_execution(request={"name": execution_resource_name})
    return execution.state


def mark_workflow_as_finished(
    execution_resource_name: str, execution_state: executions.Execution.State
):
    workflow = Workflow.objects.get(execution_resource_name=execution_resource_name)
    if execution_state == executions.Execution.State.SUCCEEDED:
        workflow.status = Workflow.SUCCESS
    else:
        workflow.status = Workflow.FAILED

    workflow.save()


def cpu_usage(value, user) -> int:
    running_environments = get_active_environments(user)
    cpu = sum(environment.instance_type.cpus() for environment in running_environments)
    return value + cpu


def exceeded_quotas(user) -> Iterable[str]:
    quotas_exceeded = []
    # Check if user has exceeded MAX_RUNNING_ENVIRONMENTS
    running_workspaces = get_workspaces_list(user)
    if len(running_workspaces) >= constants.MAX_RUNNING_WORKSPACES:
        quotas_exceeded.append(
            f"You can only have {constants.MAX_RUNNING_WORKSPACES} running workspaces."
        )

    return quotas_exceeded
