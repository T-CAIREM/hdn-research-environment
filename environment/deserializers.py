from typing import Iterable, Optional

from django.apps import apps

from environment.entities import (
    EntityScaffolding,
    EnvironmentStatus,
    EnvironmentType,
    Region,
    ResearchEnvironment,
    ResearchWorkspace,
    Workflow,
    WorkflowStatus,
    WorkflowType,
    WorkspaceStatus,
    SharedWorkspace,
    SharedBucket,
    SharedBucketObject,
    WorkspaceType,
    QuotaInfo,
    CloudRole,
    DatasetsMonitoringEntry,
)

PublishedProject = apps.get_model("project", "PublishedProject")


def _check_billing_accessibility(billing_info: dict, user_billing_accounts: list = None) -> tuple[bool, str]:
    """
    Check if the billing account is accessible by the user.
    Returns (is_accessible, reason_if_not_accessible)
    """
    billing_account_id = billing_info.get("billing_account_id")
    billing_enabled = billing_info.get("billing_enabled", False)
    
    if not billing_account_id:
        return False, "No billing account connected"
    
    if not billing_enabled:
        return False, "Billing account is closed or inactive"
    
    # Check if user has access to this billing account
    if user_billing_accounts:
        accessible_billing_ids = [acc.get("id") for acc in user_billing_accounts]
        if billing_account_id not in accessible_billing_ids:
            return False, "Billing account access revoked"
    
    return True, None


def _check_workspace_accessibility(
    billing_info: dict, 
    workbenches: list, 
    projects: Iterable[PublishedProject], 
    user_billing_accounts: list = None
) -> tuple[bool, str]:
    """
    Check overall workspace accessibility including billing and project access.
    Returns (is_accessible, reason_if_not_accessible)
    """
    # First check billing accessibility
    billing_accessible, billing_reason = _check_billing_accessibility(billing_info, user_billing_accounts)
    
    # Check if any workbenches have inaccessible projects
    project_access_issues = []
    for workbench in workbenches:
        if workbench.get("type") == "Workbench":
            dataset_id = workbench.get("dataset_identifier")
            if dataset_id:
                project = _get_project_for_environment(dataset_id, projects)
                if not project:
                    project_access_issues.append(f"Dataset '{dataset_id}' access revoked")
    
    # Determine overall accessibility and reason
    if not billing_accessible and project_access_issues:
        return False, f"{billing_reason}; {'; '.join(project_access_issues)}"
    if not billing_accessible:
        return False, billing_reason
    if project_access_issues:
        return False, "; ".join(project_access_issues)
    
    return True, None


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


def deserialize_research_environments(
    workbenches: dict,
    gcp_project_id: str,
    region: Region,
    projects: Iterable[PublishedProject],
) -> Iterable[ResearchEnvironment]:
    return [
        ResearchEnvironment(
            gcp_identifier=workbench["gcp_identifier"],
            dataset_identifier=workbench["dataset_identifier"],
            url=workbench.get("url"),
            workspace_name=gcp_project_id,
            status=EnvironmentStatus(workbench["status"]),
            cpu=workbench["cpu"],
            memory=workbench["memory"],
            region=region,
            type=EnvironmentType(workbench["workbench_type"]),
            machine_type=workbench["machine_type"],
            disk_size=workbench.get("disk_size"),
            project=_get_project_for_environment(
                workbench["dataset_identifier"], projects
            ),
            gpu_accelerator_type=workbench.get("gpu_accelerator_type"),
            service_account_name=workbench.get("service_account_name"),
            workbench_owner_username=workbench.get("workbench_owner_username"),
        )
        if workbench.get("type") == "Workbench"
        else deserialize_entity_scaffolding(workbench)
        for workbench in workbenches
    ]


def deserialize_workflow_details(workflow_data: dict) -> Workflow:
    return Workflow(
        id=workflow_data["id"],
        type=WorkflowType(workflow_data["build_type"]),
        status=WorkflowStatus(workflow_data["status"]),
        error_information=workflow_data["error"],
        workspace_id=workflow_data["workspace_id"],
    )


def deserialize_workspace_details(
    data: dict, projects: Iterable[PublishedProject], user_billing_accounts: list = None
) -> ResearchWorkspace:
    workspace_accessible, access_denial_reason = _check_workspace_accessibility(
        data["billing_info"], data["workbenches"], projects, user_billing_accounts
    )
    
    return ResearchWorkspace(
        region=Region(data["region"]),
        gcp_project_id=data["gcp_project_id"],
        gcp_billing_id=data["billing_info"]["billing_account_id"],
        status=WorkspaceStatus(data["status"]),
        is_owner=data["is_owner"],
        workbenches=deserialize_research_environments(
            data["workbenches"],
            data["gcp_project_id"],
            Region(data["region"]),
            projects,
        ),
        is_accessible=workspace_accessible,
        access_denial_reason=access_denial_reason,
    )


def deserialize_shared_bucket_details(buckets_data: dict) -> Iterable[SharedBucket]:
    return [
        SharedBucket(
            name=data["bucket_name"],
            is_owner=data["is_owner"],
            is_admin=data["is_admin"],
        )
        for data in buckets_data
    ]


def deserialize_shared_workspace_details(data: dict, user_billing_accounts: list = None) -> SharedWorkspace:
    billing_accessible, access_denial_reason = _check_billing_accessibility(
        data["billing_info"], user_billing_accounts
    )
    
    return SharedWorkspace(
        gcp_project_id=data["gcp_project_id"],
        gcp_billing_id=data["billing_info"]["billing_account_id"],
        status=WorkspaceStatus(data["status"]),
        buckets=deserialize_shared_bucket_details(data["buckets"]),
        is_owner=data["is_owner"],
        is_accessible=billing_accessible,
        access_denial_reason=access_denial_reason,
    )


def deserialize_entity_scaffolding(data: dict) -> EntityScaffolding:
    return EntityScaffolding(
        gcp_project_id=data["gcp_project_id"], status=EnvironmentStatus(data["status"])
    )


def deserialize_workspaces(
    data: dict, projects: Iterable[PublishedProject], user_billing_accounts: list
) -> Iterable[ResearchWorkspace]:
    return [
        deserialize_workspace_details(workspace_data, projects, user_billing_accounts)
        if WorkspaceType(workspace_data.get("type")) == WorkspaceType.WORKSPACE
        else deserialize_entity_scaffolding(workspace_data)
        for workspace_data in data
    ]


def deserialize_shared_workspaces(data: dict, user_billing_accounts: list) -> Iterable[SharedWorkspace]:
    return [
        deserialize_shared_workspace_details(workspace_data, user_billing_accounts)
        if WorkspaceType(workspace_data.get("type")) == WorkspaceType.SHARED_WORKSPACE
        else deserialize_entity_scaffolding(workspace_data)
        for workspace_data in data
    ]


def _get_project_for_environment(
    dataset_identifier: str,
    projects: Iterable[PublishedProject],
) -> Optional[PublishedProject]:
    try:
        return next(
            iter(
                project
                for project in projects
                if _project_data_group(project) == dataset_identifier
            )
        )
    except StopIteration:
        return None


def deserialize_shared_bucket_objects(data: dict) -> Iterable[SharedBucketObject]:
    return [
        SharedBucketObject(
            type=bucket_object["type"],
            name=bucket_object["name"],
            size=bucket_object["size"],
            modification_time=bucket_object["modification_time"],
            full_path=bucket_object["full_path"],
        )
        for bucket_object in data
    ]


def deserialize_quotas(data) -> Iterable[QuotaInfo]:
    return [
        QuotaInfo(
            metric_name=quota["metric_name"],
            limit=quota["limit"],
            usage=quota["usage"],
            usage_percentage=(quota["usage"] / quota["limit"]) * 100,
        )
        for quota in data
    ]


def deserialize_cloud_roles(data: dict) -> Iterable[CloudRole]:
    return [
        CloudRole(
            full_name=role_object["full_name"],
            title=role_object["title"],
            description=role_object["description"],
        )
        for role_object in data
    ]


def deserialize_datasets_monitoring_data(data) -> Iterable[DatasetsMonitoringEntry]:
    return [
        DatasetsMonitoringEntry(
            dataset_identifier=entry["dataset_identifier"],
            instance_type=entry["instance_type"],
            total_time=entry["total_time"],
            user_email=entry["user_email"],
        )
        for entry in data
    ]
