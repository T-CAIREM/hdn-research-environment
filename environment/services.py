import logging
import traceback
from collections import defaultdict
from typing import Any, Dict, Iterable, Optional, Tuple

from django.apps import apps
from django.contrib.sites.shortcuts import get_current_site
from django.db.models import Model, Q

import environment.constants as constants
import environment.mailers as mailers
from environment import api
from environment.decorators import handle_api_error
from environment.deserializers import (
    _project_data_group,
    deserialize_cloud_roles,
    deserialize_datasets_monitoring_data,
    deserialize_quotas,
    deserialize_shared_bucket_objects,
    deserialize_shared_workspaces,
    deserialize_simplified_workspace,
    deserialize_workflow_details,
    deserialize_workspaces, deserialize_shared_bucket_details,
)
from environment.entities import (
    DatasetsMonitoringEntry,
    QuotaInfo,
    ResearchEnvironment,
    ResearchWorkspace,
    SharedBucket,
    SharedBucketObject,
    SharedWorkspace,
)
from environment.entities import Workflow as ApiWorkflow
from environment.exceptions import (
    AddRolesToCloudGroupFailed,
    AddWorkbenchCollaboratorFailed,
    BillingAccessRevokationFailed,
    BillingSharingFailed,
    BucketAccessRevokationFailed,
    BucketSharingFailed,
    ChangeEnvironmentInstanceTypeFailed,
    CreateCloudGroupFailed,
    CreateSharedBucketDirectoryFailed,
    CreateSharedBucketFailed,
    CreateWorkspaceFailed,
    DeleteCloudGroupFailed,
    DeleteEnvironmentFailed,
    DeleteSharedBucketContentFailed,
    DeleteSharedBucketFailed,
    DeleteWorkspaceFailed,
    EnvironmentCreationFailed,
    GenerateSignedUrlFailed,
    GetAvailableEnvironmentsFailed,
    GetBillingAccountsListFailed,
    GetGroupIAMRolesFailed,
    GetGroupsIAMRolesFailed,
    GetMonitoringDatasetsFailed,
    GetSharedBucketContentFailed,
    GetSharedBucketFailed,
    GetSimplifiedWorkspaceFailed,
    GetWorkflowFailed,
    IdentityProvisioningFailed,
    InvitedUserIsAccountOwner,
    ListGroupRolesFailed,
    RemoveRolesFromCloudGroupFailed,
    RemoveWorkbenchCollaboratorFailed,
    RenewEnvironmentCertificateFailed,
    GetSharedBucketFailed,
    GetSimplifiedWorkspaceFailed,
    GetSharedBucketFailed,
    GetSimplifiedWorkspaceFailed,
    PublishedProjectAccessFailed,
    StartEnvironmentFailed,
    StopEnvironmentFailed,
    UpdateWorkspaceBillingAccountFailed,
)
from environment.models import (
    BillingAccountSharingInvite,
    BucketSharingInvite,
    CloudGroup,
    CloudIdentity,
    VMInstance,
    Workflow,
)
from environment.utilities import inner_join_iterators, left_join_iterators
from project.authorization.access import can_access_project

PublishedProject = apps.get_model("project", "PublishedProject")
UserModel = apps.get_model("user", "User")


User = Model


DEFAULT_REGION = "us-central1"


logger = logging.getLogger(__name__)


def _environment_data_group(environment: ResearchEnvironment) -> str:
    return environment.dataset_identifier


@handle_api_error(
    "Cloud Identity Creation",
    IdentityProvisioningFailed,
    lambda user, password, recovery_email: {
        "user_id": user.username,
        "recovery_email": recovery_email,
    },
)
def create_cloud_identity(
    user: User, password: str, recovery_email: str
) -> CloudIdentity:
    gcp_user_id = user.username
    response = api.create_cloud_identity(
        gcp_user_id,
        user.profile.first_names,
        user.profile.last_name,
        password,
        recovery_email,
    )
    body = response.json()
    identity = CloudIdentity.objects.create(
        user=user,
        gcp_user_id=gcp_user_id,
        email=body["primary_email"],
    )
    return identity


@handle_api_error(
    "Billing Accounts List Retrieval",
    GetBillingAccountsListFailed,
    lambda user: {"user_email": user.cloud_identity.email},
)
def get_billing_accounts_list(user: User) -> list[dict]:
    response = api.list_billing_accounts(user.cloud_identity.email)
    return response.json()


def is_billing_account_owner(user: User, billing_account_id: str):
    billing_account_list = get_billing_accounts_list(user)
    for billing_account in billing_account_list:
        if (
            billing_account["id"] == billing_account_id
            and billing_account["is_owner"] is True
        ):
            return True

    return False


def is_shared_bucket_owner(
    shared_workspaces_list: Iterable[SharedWorkspace], shared_bucket_name: str
):
    return any(
        bucket.name == shared_bucket_name and bucket.is_owner is True
        for workspace in shared_workspaces_list
        for bucket in workspace.buckets
    )


def is_shared_bucket_admin(
    shared_workspaces_list: Iterable[SharedWorkspace], shared_bucket_name: str
):
    return any(
        bucket.name == shared_bucket_name and bucket.is_admin
        for workspace in shared_workspaces_list
        for bucket in workspace.buckets
    )


def is_environment_owner(user: User, workbench_owner_username: str) -> bool:
    return workbench_owner_username == user.username


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
    if invite.owner == user:
        raise InvitedUserIsAccountOwner
    invite.user = user
    invite.save()

    return invite


def consume_bucket_sharing_token(user: User, token: str) -> BucketSharingInvite:
    invite = BucketSharingInvite.objects.get(token=token, is_revoked=False)
    invite.user = user
    share_bucket(
        owner_email=invite.owner.cloud_identity.email,
        user_email=invite.user.cloud_identity.email,
        bucket_name=invite.shared_bucket_name,
        workspace_project_id=invite.shared_workspace_name,
        permissions=invite.permissions,
    )
    invite.is_consumed = True
    invite.save()
    return invite


@handle_api_error(
    "Billing Account Sharing",
    BillingSharingFailed,
    lambda owner_email, user_email, billing_account_id: {
        "owner_email": owner_email,
        "user_email": user_email,
        "billing_account_id": billing_account_id,
    },
)
def share_billing_account(owner_email: str, user_email: str, billing_account_id: str):
    response = api.share_billing_account(
        owner_email=owner_email,
        user_email=user_email,
        billing_account_id=billing_account_id,
    )
    return response


def revoke_billing_account_access(billing_account_sharing_invite_id: int):
    billing_account_sharing_invite = BillingAccountSharingInvite.objects.select_related(
        "owner__cloud_identity", "user__cloud_identity"
    ).get(pk=billing_account_sharing_invite_id)
    billing_account_sharing_invite.is_revoked = True
    billing_account_sharing_invite.save()

    if billing_account_sharing_invite.is_consumed:
        _revoke_consumed_billing_account_access(billing_account_sharing_invite)


@handle_api_error(
    "Billing Account Access Revocation",
    BillingAccessRevokationFailed,
    lambda billing_account_sharing_invite: {
        "owner_email": billing_account_sharing_invite.owner.cloud_identity.email,
        "user_email": billing_account_sharing_invite.user.cloud_identity.email,
        "billing_account_id": billing_account_sharing_invite.billing_account_id,
    },
)
def _revoke_consumed_billing_account_access(
    billing_account_sharing_invite: BillingAccountSharingInvite,
):
    owner_email = billing_account_sharing_invite.owner.cloud_identity.email
    user_email = billing_account_sharing_invite.user.cloud_identity.email
    billing_account_id = billing_account_sharing_invite.billing_account_id

    response = api.revoke_billing_account_access(
        owner_email=owner_email,
        user_email=user_email,
        billing_account_id=billing_account_id,
    )
    return response


def invite_user_to_shared_bucket(
    request,
    owner: User,
    user_email: str,
    shared_bucket_name: str,
    shared_workspace_name: str,
    permissions: str,
) -> BucketSharingInvite:
    invite = BucketSharingInvite.objects.create(
        owner=owner,
        shared_bucket_name=shared_bucket_name,
        user_contact_email=user_email,
        shared_workspace_name=shared_workspace_name,
        permissions=permissions,
    )
    site_domain = get_current_site(request).domain
    mailers.send_bucket_sharing_confirmation(site_domain=site_domain, invite=invite)
    return invite


@handle_api_error(
    "Workspace Creation",
    CreateWorkspaceFailed,
    lambda user, billing_account_id: {
        "user_email": user.cloud_identity.email,
        "billing_account_id": billing_account_id,
    },
  
)
def create_workspace(user: User, billing_account_id: str):
    response = api.create_workspace(
        email=user.cloud_identity.email,
        billing_account_id=billing_account_id,
        user_groups=list(
            user.cloud_identity.user_groups.all().values_list("name", flat=True)
        ),
    )
    data = response.json()
    persist_workflow(user=user, workflow_id=data["workflow_id"])
    return response


@handle_api_error(
    "Shared Workspace Creation",
    CreateWorkspaceFailed,
    lambda user, billing_account_id: {
        "user_email": user.cloud_identity.email,
        "billing_account_id": billing_account_id,
    },
)
def create_shared_workspace(user: User, billing_account_id: str):
    response = api.create_shared_workspace(
        user_email=user.cloud_identity.email,
        billing_account_id=billing_account_id,
    )
    data = response.json()
    persist_workflow(user=user, workflow_id=data["workflow_id"])
    return response


@handle_api_error(
    "Workspace Deletion",
    DeleteWorkspaceFailed,
    lambda user, billing_account_id, gcp_project_id: {
        "user_email": user.cloud_identity.email,
        "gcp_project_id": gcp_project_id,
        "billing_account_id": billing_account_id,
    },
)
def delete_workspace(
    user: User, billing_account_id: str, gcp_project_id: str
):
    response = api.delete_workspace(
        email=user.cloud_identity.email,
        gcp_project_id=gcp_project_id,
        billing_account_id=billing_account_id,
    )
    data = response.json()
    persist_workflow(user=user, workflow_id=data["workflow_id"])
    return response


@handle_api_error(
    "Shared Workspace Deletion",
    DeleteWorkspaceFailed,
    lambda user, billing_account_id, gcp_project_id: {
        "user_email": user.cloud_identity.email,
        "gcp_project_id": gcp_project_id,
        "billing_account_id": billing_account_id,
    },
)
def delete_shared_workspace(user: User, billing_account_id: str, gcp_project_id: str):
    response = api.delete_shared_workspace(
        user_email=user.cloud_identity.email,
        workspace_project_id=gcp_project_id,
        billing_account_id=billing_account_id,
    )
    data = response.json()
    persist_workflow(user=user, workflow_id=data["workflow_id"])
    return response


def _create_workbench_kwargs(
    user: User,
    project: Any,
    workspace_project_id: str,
    machine_type: VMInstance,
    workbench_type: str,
    disk_size: int,
    region: str,
    gpu_accelerator_type: Optional[str] = None,
    sharing_bucket_identifiers: Optional[list[str]] = None,
    collaborators: Optional[list[str]] = None,
) -> dict:
    user_email = user.cloud_identity.email

    return {
        "user_email": user_email,
        "workspace_project_id": workspace_project_id,
        "workbench_type": workbench_type,
        "machine_type": machine_type.get_instance_value(),
        "memory": machine_type.memory,
        "cpu": machine_type.cpu,
        "dataset_identifier": _project_data_group(project),
        "disk_size": disk_size,
        "region": region,
        "bucket_name": project.project_file_root(),
        "gpu_accelerator_type": gpu_accelerator_type,
        "sharing_bucket_identifiers": (
            sharing_bucket_identifiers if sharing_bucket_identifiers else []
        ),
        "user_groups": list(
            user.cloud_identity.user_groups.all().values_list("name", flat=True)
        ),
        "collaborators": collaborators,
    }


@handle_api_error(
    "Research Environment Creation",
    EnvironmentCreationFailed,
    lambda user, project, workspace_project_id, machine_type, workbench_type, disk_size, gpu_accelerator_type=None, sharing_bucket_identifiers=None, collaborators=None: {
        "user_email": user.cloud_identity.email,
        "workspace_project_id": workspace_project_id,
        "workbench_type": workbench_type,
        "machine_type": machine_type.get_instance_value(),
    },
)
def create_research_environment(
    user: User,
    project: Any,
    workspace_project_id: str,
    machine_type: VMInstance,
    workbench_type: str,
    disk_size: int,
    region: str,
    gpu_accelerator_type: Optional[str] = None,
    sharing_bucket_identifiers: Optional[list[str]] = None,
    collaborators: Optional[list[str]] = None,
) -> str:
    kwargs = _create_workbench_kwargs(
        user,
        project,
        workspace_project_id,
        machine_type,
        workbench_type,
        disk_size,
        region,
        gpu_accelerator_type,
        sharing_bucket_identifiers,
        collaborators,
    )
    response = api.create_workbench(**kwargs)
    data = response.json()
    persist_workflow(user=user, workflow_id=data["workflow_id"])
    return data


def get_available_projects(user: User) -> Iterable[Any]:
    return PublishedProject.objects.accessible_by(user)


def get_project(project_id: str) -> Any:
    return PublishedProject.objects.get(id=project_id)


def get_collaborator_user_by_email(email: str):
    return (
        UserModel.objects.only("id", "is_credentialed")
        .filter(cloud_identity__email=email)
        .first()
    )


def check_collaborator_project_access(collaborator_email: str, project_id: str) -> bool:
    collaborator_user = get_collaborator_user_by_email(collaborator_email)
    if not collaborator_user:
        return
    project = get_project(project_id)
    if not can_access_project(project, collaborator_user):
        raise PublishedProjectAccessFailed(
            f"User '{collaborator_email}' cannot be added as a collaborator because the user does not have access to the chosen project."
        )
    return True


def _get_projects_for_environments(
    environments: Iterable[ResearchEnvironment],
) -> Iterable[Any]:
    dataset_identifiers = list(map(_environment_data_group, environments))
    # FIXME: Given the fact that the groups are generated automatically in a non-reversible way,
    # the only way to match the projects to their environments is to fetch all the records and
    # calculate the group name for each of them.
    return [
        project
        for project in PublishedProject.objects.all()
        if _project_data_group(project) in dataset_identifiers
    ]


def _get_project_for_environment(
    dataset_identifier: str,
    projects: Iterable[Any],
) -> Any:
    return next(
        iter(
            project
            for project in projects
            if _project_data_group(project) == dataset_identifier
        )
    )


@handle_api_error(
    "Available Environments Retrieval",
    GetAvailableEnvironmentsFailed,
    lambda user: {"user_email": user.cloud_identity.email},
)
def get_active_environments(user: User) -> Iterable[ResearchEnvironment]:
    email = user.cloud_identity.email
    projects = PublishedProject.objects.accessible_by(user)
    # user_billing_accounts = get_billing_accounts_list(user)  # No longer needed for deserialization

    response = api.get_workspace_list(email)
    data = response.json()
    # Process through full workspace deserialization to capture all service errors
    workspaces = deserialize_workspaces(data, projects)

    # Extract all environments from all workspaces
    all_environments = []
    for workspace in workspaces:
        if hasattr(workspace, "workbenches") and workspace.workbenches:
            all_environments.extend(workspace.workbenches)

    return [environment for environment in all_environments if environment.is_active]


def get_environments_with_projects(
    user: User,
) -> Iterable[Tuple[ResearchEnvironment, Any, Iterable[Workflow]]]:
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
) -> Iterable[Tuple[Any, Optional[ResearchEnvironment], Iterable[Workflow]]]:
    available_projects = get_available_projects(user)
    project_environment_pairs = left_join_iterators(
        _project_data_group,
        available_projects,
        environments,
    )
    return [
        (project, environment, project.workflows.in_progress().filter(user=user))
        for project, environment in project_environment_pairs
    ]


def get_projects_with_environment_being_created(
    project_environment_workflow_triplets: Iterable[
        Tuple[Any, Optional[ResearchEnvironment], Iterable[Workflow]]
    ],
) -> Iterable[Tuple[None, Any, Iterable[Workflow]]]:
    return [
        (environment, project, workflows)
        for project, environment, workflows in project_environment_workflow_triplets
        if environment is None and workflows.exists()
    ]


def get_workspace_workflows(user: User) -> Iterable[Workflow]:
    return Workflow.objects.filter(
        (Q(type=Workflow.WORKSPACE_CREATE) | Q(type=Workflow.WORKSPACE_DESTROY))
        & Q(user=user, status=Workflow.INPROGRESS)
    )


def get_environment_project_pairs_with_expired_access(
    user: User,
) -> Iterable[Tuple[ResearchEnvironment, Any]]:
    all_environment_project_pairs = get_environments_with_projects(user)
    return [
        (environment, project)
        for environment, project in all_environment_project_pairs
        if not project.has_access(user)
    ]


def sort_environments_per_workspace(
    environment_project_workflow_triplets: Iterable[
        Tuple[ResearchEnvironment, Any, Iterable[Workflow]]
    ],
    workspaces: Iterable[ResearchWorkspace],
) -> Dict[
    ResearchWorkspace,
    Tuple[ResearchEnvironment, Any, Iterable[Workflow]],
]:
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
        workspace: sorted_environments_project_workflow_triplets[
            workspace.gcp_project_id
        ]
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


@handle_api_error(
    "Workspaces List Retrieval",
    GetAvailableEnvironmentsFailed,
    lambda user: {"user_email": user.cloud_identity.email},
)
def get_workspaces_list(user: User) -> Iterable[ResearchWorkspace]:
    email = user.cloud_identity.email
    projects = PublishedProject.objects.accessible_by(user)
    response = api.get_workspace_list(email)
    data = response.json()
    return deserialize_workspaces(data, projects)


@handle_api_error(
    "Quotas Data Retrieval",
    GetAvailableEnvironmentsFailed,
    lambda workspace_project_id: {
        "workspace_project_id": workspace_project_id,
    },
)
def list_quotas_data(workspace_project_id: str) -> Iterable[QuotaInfo]:
    response = api.list_quotas_data(workspace_project_id)
    data = response.json()
    return deserialize_quotas(data)


@handle_api_error(
    "Shared Workspaces List Retrieval",
    GetAvailableEnvironmentsFailed,
    lambda user: {"user_email": user.cloud_identity.email},
)
def get_shared_workspaces_list(user: User) -> Iterable[SharedWorkspace]:
    response = api.get_shared_workspaces(user.cloud_identity.email)
    data = response.json()
    return deserialize_shared_workspaces(data)


def get_shared_buckets(shared_workspaces: list[SharedWorkspace]) -> list[SharedBucket]:
    return [
        bucket
        for shared_workspace in shared_workspaces
        for bucket in shared_workspace.buckets
    ]


@handle_api_error(
    "Environment Stop",
    StopEnvironmentFailed,
    lambda workbench_type, workbench_resource_id, user, workspace_project_id: {
        "workbench_type": workbench_type,
        "workbench_resource_id": workbench_resource_id,
        "user_email": user.cloud_identity.email,
        "workspace_project_id": workspace_project_id,
    },
)
def stop_running_environment(
    workbench_type: str,
    workbench_resource_id: str,
    user: User,
    workspace_project_id: str,
) -> str:
    response = api.stop_workbench(
        workbench_type=workbench_type,
        workbench_resource_id=workbench_resource_id,
        user_email=user.cloud_identity.email,
        workspace_project_id=workspace_project_id,
    )
    data = response.json()
    persist_workflow(user=user, workflow_id=data["workflow_id"])
    return data


@handle_api_error(
    "Environment Start",
    StartEnvironmentFailed,
    lambda workbench_type, workbench_resource_id, user, workspace_project_id: {
        "workbench_type": workbench_type,
        "workbench_resource_id": workbench_resource_id,
        "user_email": user.cloud_identity.email,
        "workspace_project_id": workspace_project_id,
    },
)
def start_stopped_environment(
    workbench_type: str,
    workbench_resource_id: str,
    user: User,
    workspace_project_id: str,
) -> str:
    response = api.start_workbench(
        workbench_type=workbench_type,
        workbench_resource_id=workbench_resource_id,
        user_email=user.cloud_identity.email,
        workspace_project_id=workspace_project_id,
    )
    data = response.json()
    persist_workflow(user=user, workflow_id=data["workflow_id"])
    return data


@handle_api_error(
    "Environment Instance Type Change",
    ChangeEnvironmentInstanceTypeFailed,
    lambda user, workspace_project_id, machine_type, workbench_type, workbench_resource_id: {
        "workbench_type": workbench_type,
        "machine_type": machine_type,
        "user_email": user.cloud_identity.email,
        "workspace_project_id": workspace_project_id,
        "workbench_resource_id": workbench_resource_id,
    },
)
def change_environment_machine_type(
    user: User,
    workspace_project_id: str,
    machine_type: str,
    workbench_type: str,
    workbench_resource_id: str,
) -> str:
    response = api.change_workbench_machine_type(
        workbench_type=workbench_type,
        machine_type=machine_type,
        user_email=user.cloud_identity.email,
        workspace_project_id=workspace_project_id,
        workbench_resource_id=workbench_resource_id,
    )
    data = response.json()
    persist_workflow(user=user, workflow_id=data["workflow_id"])
    return data


@handle_api_error(
    "Environment Deletion",
    DeleteEnvironmentFailed,
    lambda user, workspace_project_id, workbench_type, workbench_resource_id: {
        "workbench_type": workbench_type,
        "user_email": user.cloud_identity.email,
        "workspace_project_id": workspace_project_id,
        "workbench_resource_id": workbench_resource_id,
    },
)
def delete_environment(
    user: User,
    workspace_project_id: str,
    workbench_type: str,
    workbench_resource_id: str,
) -> str:
    response = api.delete_workbench(
        workbench_type=workbench_type,
        user_email=user.cloud_identity.email,
        workspace_project_id=workspace_project_id,
        workbench_resource_id=workbench_resource_id,
    )
    data = response.json()
    persist_workflow(user=user, workflow_id=data["workflow_id"])
    return data


def renew_environment_certificate(
    user: User,
    workspace_project_id: str,
    workbench_resource_id: str,
) -> str:
    response = api.renew_environment_certificate(
        user_email=user.cloud_identity.email,
        workspace_project_id=workspace_project_id,
        workbench_resource_id=workbench_resource_id,
    )
    if not response.ok:
        error_message = response.json()["error"]
        logger.error(f"RenewEnvironmentCertificateFailed: {error_message}")
        raise RenewEnvironmentCertificateFailed(error_message)

    persist_workflow(user=user, workflow_id=response.json()["workflow_id"])

    return response.json()


@handle_api_error(
    "Shared Bucket Creation",
    CreateSharedBucketFailed,
    lambda region, workspace_project_id, user_defined_bucket_name, user: {
        "region": region,
        "user_email": user.cloud_identity.email,
        "user_defined_bucket_name": user_defined_bucket_name,
        "workspace_project_id": workspace_project_id,
    },
)
def create_shared_bucket(
    region: str,
    workspace_project_id: str,
    user_defined_bucket_name: str,
    user: User,
):
    response = api.create_shared_bucket(
        region=region,
        user_email=user.cloud_identity.email,
        user_defined_bucket_name=user_defined_bucket_name,
        workspace_project_id=workspace_project_id,
    )
    return response


@handle_api_error(
    "Shared Bucket Deletion",
    DeleteSharedBucketFailed,
    lambda bucket_name: {"bucket_name": bucket_name},
)
def delete_shared_bucket(bucket_name: str):
    response = api.delete_shared_bucket(
        bucket_name=bucket_name,
    )
    return response


@handle_api_error(
    "Bucket Sharing",
    BucketSharingFailed,
    lambda owner_email, user_email, bucket_name, workspace_project_id, permissions: {
        "owner_email": owner_email,
        "user_email": user_email,
        "bucket_name": bucket_name,
        "workspace_project_id": workspace_project_id,
        "permissions": permissions,
    },
)
def share_bucket(
    owner_email: str,
    user_email: str,
    bucket_name: str,
    workspace_project_id: str,
    permissions: str,
):
    response = api.share_bucket(
        owner_email=owner_email,
        user_email=user_email,
        bucket_name=bucket_name,
        workspace_project_id=workspace_project_id,
        permissions=permissions,
    )
    return response


def revoke_shared_bucket_access(bucket_sharing_invite_id: str):
    bucket_sharing_invite = BucketSharingInvite.objects.select_related(
        "owner__cloud_identity", "user__cloud_identity"
    ).get(pk=bucket_sharing_invite_id)
    bucket_sharing_invite.is_revoked = True
    bucket_sharing_invite.save()

    if bucket_sharing_invite.is_consumed:
        _revoke_consumed_shared_bucket_access(bucket_sharing_invite)


@handle_api_error(
    "Bucket Access Revocation",
    BucketAccessRevokationFailed,
    lambda bucket_sharing_invite: {
        "owner_email": bucket_sharing_invite.owner.cloud_identity.email,
        "user_email": bucket_sharing_invite.user.cloud_identity.email,
        "bucket_name": bucket_sharing_invite.shared_bucket_name,
    },
)
def _revoke_consumed_shared_bucket_access(bucket_sharing_invite: BucketSharingInvite):
    response = api.revoke_shared_bucket_access(
        owner_email=bucket_sharing_invite.owner.cloud_identity.email,
        user_email=bucket_sharing_invite.user.cloud_identity.email,
        bucket_name=bucket_sharing_invite.shared_bucket_name,
    )
    return response


def get_owned_shares_of_bucket(owner: User, shared_bucket_name: str):
    return owner.owner_bucketsharinginvite_set.filter(
        shared_bucket_name=shared_bucket_name, is_revoked=False
    )


@handle_api_error(
    "Workflow Retrieval",
    GetWorkflowFailed,
    lambda execution_resource_name: {
        "execution_resource_name": execution_resource_name
    },
)
def get_execution(execution_resource_name) -> ApiWorkflow:
    response = api.get_workflow(execution_resource_name)
    data = response.json()
    if data:
        return deserialize_workflow_details(data)


def mark_workflow_as_finished(execution_resource_name: str):
    workflow = Workflow.objects.get(execution_resource_name=execution_resource_name)
    workflow.in_progress = False
    workflow.save()


def cpu_usage(workspaces: Iterable[ResearchWorkspace]) -> int:
    workbenches = [
        workbench
        for workspace in workspaces
        if hasattr(
            workspace, "workbenches"
        )  # HACK: Workspace scaffolding do not have the workbenches attribute.
        for workbench in workspace.workbenches
        if hasattr(
            workbench, "machine_type"
        )  # HACK: Workbench scaffoldings do not have the machine type attribute.
    ]
    return sum(workbench.cpu for workbench in workbenches)


def exceeded_quotas(user) -> Iterable[str]:
    quotas_exceeded = []
    # Check if user has exceeded MAX_RUNNING_ENVIRONMENTS
    running_workspaces = get_workspaces_list(user)
    if len(running_workspaces) >= constants.MAX_RUNNING_WORKSPACES:
        quotas_exceeded.append(
            f"You can only have {constants.MAX_RUNNING_WORKSPACES} running workspaces."
        )

    return quotas_exceeded


def persist_workflow(user: User, workflow_id: str):
    Workflow.objects.create(
        user=user,
        execution_resource_name=workflow_id,
        in_progress=True,
    )


def get_running_workflows(user: User):
    return Workflow.objects.filter(user=user, in_progress=True)


@handle_api_error(
    "Signed URL Generation",
    GenerateSignedUrlFailed,
    lambda bucket_name, size, filename, user: {
        "bucket_name": bucket_name,
        "size": size,
        "filename": filename,
        "user_email": user.cloud_identity.email,
    },
)
def generate_signed_url(bucket_name: str, size: int, filename: str, user: User) -> str:
    user_email = user.cloud_identity.email
    response = api.generate_signed_url(
        bucket_name=bucket_name,
        size=size,
        filename=filename,
        user_email=user_email,
    )
    data = response.json()
    return data["signed_url"]


@handle_api_error(
    "Shared Bucket Content Retrieval",
    GetSharedBucketContentFailed,
    lambda bucket_name, user, subdir="": {
        "bucket_name": bucket_name,
        "subdir": subdir,
        "user_email": user.cloud_identity.email,
    },
)
def get_shared_bucket_content(
    bucket_name: str, user: User, subdir: str = ""
) -> Iterable[SharedBucketObject]:
    user_email = user.cloud_identity.email
    response = api.get_shared_bucket_content(
        bucket_name=bucket_name, subdir=subdir, user_email=user_email
    )
    data = response.json()
    return deserialize_shared_bucket_objects(data)


@handle_api_error(
    "Shared Bucket Directory Creation",
    CreateSharedBucketDirectoryFailed,
    lambda bucket_name, parent_path, directory_name, user: {
        "bucket_name": bucket_name,
        "parent_path": parent_path,
        "directory_name": directory_name,
        "user_email": user.cloud_identity.email,
    },
)
def create_shared_bucket_directory(
    bucket_name: str, parent_path: str, directory_name: str, user: User
):
    user_email = user.cloud_identity.email
    response = api.create_shared_bucket_directory(
        bucket_name=bucket_name,
        parent_path=parent_path,
        directory_name=directory_name,
        user_email=user_email,
    )
    return response


@handle_api_error(
    "Shared Bucket Content Deletion",
    DeleteSharedBucketContentFailed,
    lambda bucket_name, full_path, user: {
        "bucket_name": bucket_name,
        "full_path": full_path,
        "user_email": user.cloud_identity.email,
    },
)
def delete_shared_bucket_content(bucket_name: str, full_path: str, user: User):
    user_email = user.cloud_identity.email
    response = api.delete_shared_bucket_content(
        bucket_name=bucket_name, full_path=full_path, user_email=user_email
    )
    return response


def add_user_to_cloud_group(user: User, cloud_group_list: list[CloudGroup]):
    for cloud_group in cloud_group_list:
        user.cloud_identity.user_groups.add(cloud_group)


def remove_user_from_cloud_group(user: User, cloud_group_list: list[CloudGroup]):
    for cloud_group in cloud_group_list:
        user.cloud_identity.user_groups.remove(cloud_group)


@handle_api_error(
    "Cloud Group Creation",
    CreateCloudGroupFailed,
    lambda group_name, description: {
        "group_name": group_name,
        "description": description,
    },
)
def create_cloud_group(group_name: str, description: str):
    response = api.create_cloud_user_group(group_name, description)
    CloudGroup.objects.create(name=group_name, description=description)
    return response


@handle_api_error(
    "Cloud Group Deletion",
    DeleteCloudGroupFailed,
    lambda group_name: {"group_name": group_name},
)
def delete_cloud_group(group_name: str):
    response = api.delete_cloud_user_group(group_name)
    CloudGroup.objects.filter(name=group_name).delete()
    return response


@handle_api_error("Cloud Group Roles List", ListGroupRolesFailed, lambda: {})
def list_cloud_group_roles():
    response = api.list_cloud_group_roles()
    data = response.json()
    return deserialize_cloud_roles(data)


@handle_api_error(
    "Cloud Group IAM Roles Retrieval",
    GetGroupIAMRolesFailed,
    lambda group_name: {"group_name": group_name},
)
def get_cloud_group_iam_roles(group_name: str):
    response = api.get_cloud_group_iam_roles(group_name)
    data = response.json()
    return deserialize_cloud_roles(data)


@handle_api_error(
    "Cloud Groups IAM Roles Retrieval", GetGroupsIAMRolesFailed, lambda: {}
)
def get_cloud_groups_iam_roles():
    response = api.get_cloud_groups_iam_roles()
    return response.json()


@handle_api_error(
    "Cloud Group Roles Addition",
    AddRolesToCloudGroupFailed,
    lambda group_name, role_list: {"group_name": group_name, "role_list": role_list},
)
def add_roles_to_cloud_group(group_name: str, role_list: list[str]):
    response = api.add_roles_to_cloud_group(group_name, role_list)
    return response


@handle_api_error(
    "Cloud Group Roles Removal",
    RemoveRolesFromCloudGroupFailed,
    lambda group_name, role_list: {"group_name": group_name, "role_list": role_list},
)
def remove_roles_from_cloud_group(group_name: str, role_list: list[str]):
    response = api.remove_roles_from_cloud_group(group_name, role_list)
    return response


def match_groups_with_roles(cloud_groups: list[CloudGroup]):
    cloud_groups_iam_list = get_cloud_groups_iam_roles()
    return {
        group: deserialize_cloud_roles(cloud_groups_iam_list.get(group.name, ""))
        for group in cloud_groups
    }


@handle_api_error(
    "Monitoring Datasets Retrieval", GetMonitoringDatasetsFailed, lambda: {}
)
def get_datasets_monitoring_data() -> Iterable[DatasetsMonitoringEntry]:
    response = api.get_datasets_monitoring_data()
    data = response.json()
    return deserialize_datasets_monitoring_data(data)


@handle_api_error(
    "Workspace Billing Account Update",
    UpdateWorkspaceBillingAccountFailed,
    lambda workspace_project_id, billing_account_id: {
        "workspace_project_id": workspace_project_id,
        "billing_account_id": billing_account_id,
    },
)
def update_workspace_billing_account(
    workspace_project_id: str, billing_account_id: str
):
    response = api.update_workspace_billing_account(
        workspace_project_id, billing_account_id
    )
    return response


def get_workbench_collaborators(
    workspace_project_id: str, service_account_name: str
) -> list:
    response = api.get_workbench_collaborators(
        workspace_project_id=workspace_project_id,
        service_account_name=service_account_name,
    )

    if not response.ok:
        try:
            error_message = response.json().get(
                "error", "Failed to fetch collaborators"
            )
        except (ValueError, TypeError):
            error_message = "Failed to fetch collaborators - Invalid response format"
        logger.error(
            f"Failed to get workbench collaborators: {error_message}",
            extra={"traceback": traceback.format_exc()},
        )
        return []

    collaborators_data = response.json()
    return collaborators_data.get("collaborators", [])


@handle_api_error(
    "Workbench Collaborator Addition",
    AddWorkbenchCollaboratorFailed,
    lambda workspace_project_id, service_account_name, collaborator_email: {
        "workspace_project_id": workspace_project_id,
        "service_account_name": service_account_name,
        "collaborator_email": collaborator_email,
    },
)
def add_workbench_collaborator(
    workspace_project_id: str, service_account_name: str, collaborator_email: str
):
    response = api.add_workbench_collaborators(
        workspace_project_id=workspace_project_id,
        service_account_name=service_account_name,
        collaborators=[collaborator_email],
    )
    return response


@handle_api_error(
    "Workbench Collaborator Removal",
    RemoveWorkbenchCollaboratorFailed,
    lambda workspace_project_id, service_account_name, collaborator_email: {
        "workspace_project_id": workspace_project_id,
        "service_account_name": service_account_name,
        "collaborator_email": collaborator_email,
    },
)
def remove_workbench_collaborator(
    workspace_project_id: str, service_account_name: str, collaborator_email: str
):
    response = api.remove_workbench_collaborators(
        workspace_project_id=workspace_project_id,
        service_account_name=service_account_name,
        collaborators=[collaborator_email],
    )
    return response


def get_workbench_notifications(
    workspace_project_id: str, service_account_name: str
) -> list:
    response = api.get_workbench_notifications(
        workspace_project_id=workspace_project_id,
        service_account_name=service_account_name,
    )

    if not response.ok:
        try:
            error_message = response.json().get(
                "error", "Failed to fetch notifications"
            )
        except (ValueError, TypeError):
            error_message = "Failed to fetch notifications - Invalid response format"
        logger.error(
            f"Failed to get workbench notifications: {error_message}",
            extra={"traceback": traceback.format_exc()},
        )
        return []

    notifications_data = response.json()
    return notifications_data.get("notifications", [])


def mark_notification_as_viewed(notification_id: int) -> bool:
    response = api.mark_notification_as_viewed(notification_id=notification_id)

    if not response.ok:
        try:
            error_message = response.json().get(
                "error", "Failed to mark notification as viewed"
            )
        except (ValueError, TypeError):
            error_message = (
                "Failed to mark notification as viewed - Invalid response format"
            )
        logger.error(
            f"Failed to mark notification as viewed: {error_message}",
            extra={"traceback": traceback.format_exc()},
        )
        return False

    return True


def clear_all_notifications(
    workspace_project_id: str, service_account_name: str
) -> bool:
    response = api.clear_all_notifications(
        workspace_project_id=workspace_project_id,
        service_account_name=service_account_name,
    )

    if not response.ok:
        try:
            error_message = response.json().get(
                "error", "Failed to clear notifications"
            )
        except (ValueError, TypeError):
            error_message = "Failed to clear notifications - Invalid response format"
        logger.error(
            f"Failed to clear notifications: {error_message}",
            extra={"traceback": traceback.format_exc()},
        )
        return False

    return True


def get_simplified_workspace(workspace_project_id: str, user: User):
    response = api.get_simplified_workspace(
        workspace_project_id, user.cloud_identity.email
    )
    if not response.ok:
        error_message = response.json()["error"]
        logger.error(f"GetSimplifiedWorkspaceFailed: {error_message}")
        raise GetSimplifiedWorkspaceFailed(error_message)
    return deserialize_simplified_workspace(response.json())


def get_shared_bucket(bucket_name: str, user: User):
    if not bucket_name:
        return
    response = api.get_shared_bucket(bucket_name, user.cloud_identity.email)
    if not response.ok:
        error_message = response.json()["error"]
        logger.error(f"GetSharedBucketFailed: {error_message}")
        raise GetSharedBucketFailed(error_message)
    return deserialize_shared_bucket_details([response.json()])[0]
