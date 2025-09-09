import logging
from typing import Iterable, Optional, List, Any

from django.apps import apps  # type: ignore
from environment.api_types import (
    RawServiceErrorsData,
    RawWorkspacesData,
    RawSharedWorkspacesData,
    RawWorkbenchesData,
    WorkspaceResponse,
    SharedWorkspaceResponse,
)

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
    ServiceError,
    SimplifiedResearchWorkspace,
)

PublishedProject = apps.get_model("project", "PublishedProject")


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
    workbenches: RawWorkbenchesData,
    gcp_project_id: str,
    region: Region,
    projects: Iterable[Any],
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
            service_account_name=workbench["service_account_name"],
            workbench_owner_username=workbench["workbench_owner_username"],
            service_errors=deserialize_service_errors(workbench.get("service_errors", [])),
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


def deserialize_service_errors(service_errors_data: RawServiceErrorsData) -> List[ServiceError]:
    service_errors = []
    # Handle case where service_errors_data might be None
    if not service_errors_data:
        return service_errors
        
    for error in service_errors_data:
        error_obj = ServiceError(
            error_type=error.get("error_type", "unknown"),
            message=error.get("message", ""),
            resource_id=error.get("resource_id", ""),
            service_name=error.get("service_name", ""),
            details=error.get("details"),
            can_retry=error.get("can_retry", False),
        )
        service_errors.append(error_obj)
    
    return service_errors


def deserialize_workspace_details(
    data: WorkspaceResponse, projects: Iterable[Any]
) -> ResearchWorkspace:
    # Handle missing or invalid billing_info gracefully
    billing_info = data.get("billing_info")
    service_errors = deserialize_service_errors(data.get("service_errors", []))

    # Safely extract billing account ID
    billing_account_id = billing_info.get("billing_account_id")

    return ResearchWorkspace(
        region=Region(data["region"]),
        gcp_project_id=data["gcp_project_id"],
        gcp_billing_id=billing_account_id,
        status=WorkspaceStatus(data["status"]),
        is_owner=data["is_owner"],
        workbenches=deserialize_research_environments(
            data["workbenches"], data["gcp_project_id"], Region(data["region"]), projects
        ),
    is_accessible=data.get("is_accessible", True),
    access_denial_reason=data.get("access_denial_reason"),
        service_errors=service_errors,
    )


def deserialize_simplified_workspace_details(data: dict) -> SimplifiedResearchWorkspace:
    return SimplifiedResearchWorkspace(
        gcp_project_id=data["gcp_project_id"],
        status=WorkspaceStatus(data["status"]),
        owner=data["owner"],
        **({"region": Region(data["region"])} if data.get("region") else {})
    )


def deserialize_shared_bucket_details(buckets_data: List[dict]) -> Iterable[SharedBucket]:
    return [
        SharedBucket(
            name=bucket["bucket_name"],
            is_owner=bucket.get("is_owner", False),
            is_admin=bucket.get("is_admin", False),
        )
        for bucket in buckets_data
    ]




def deserialize_shared_workspace_details(data: SharedWorkspaceResponse) -> SharedWorkspace:
    service_errors = deserialize_service_errors(data.get("service_errors", []))
    
    # Handle missing or invalid billing_info gracefully
    billing_info = data.get("billing_info")
    if not billing_info or not isinstance(billing_info, dict):
        billing_info = {
            "billing_account_id": None,
            "billing_enabled": False
        }
    
    # Safely extract billing account ID
    billing_account_id = billing_info.get("billing_account_id")
    
    return SharedWorkspace(
        gcp_project_id=data["gcp_project_id"],
        gcp_billing_id=billing_account_id,
        status=WorkspaceStatus(data["status"]),
        buckets=deserialize_shared_bucket_details(data["buckets"]),
        is_owner=data["is_owner"],
    is_accessible=data.get("is_accessible", True),
    access_denial_reason=data.get("access_denial_reason"),
        service_errors=service_errors,
    )


def deserialize_entity_scaffolding(data: dict) -> EntityScaffolding:
    return EntityScaffolding(
        gcp_project_id=data["gcp_project_id"], status=EnvironmentStatus(data["status"])
    )


def deserialize_workspaces(
    data: RawWorkspacesData, projects: Iterable[Any]
) -> Iterable[ResearchWorkspace]:
    return [
        deserialize_workspace_details(workspace_data, projects)
        if WorkspaceType(workspace_data.get("type")) == WorkspaceType.WORKSPACE
        else deserialize_entity_scaffolding(workspace_data)
        for workspace_data in data
    ]

def deserialize_simplified_workspace(data: dict):
    return deserialize_simplified_workspace_details(data)


def deserialize_shared_workspaces(data: RawSharedWorkspacesData) -> Iterable[SharedWorkspace]:
    return [
        deserialize_shared_workspace_details(workspace_data)
        if WorkspaceType(workspace_data.get("type")) == WorkspaceType.SHARED_WORKSPACE
        else deserialize_entity_scaffolding(workspace_data)
        for workspace_data in data
    ]


def _get_project_for_environment(
    dataset_identifier: str,
    projects: Iterable[Any],
) -> Optional[Any]:
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
