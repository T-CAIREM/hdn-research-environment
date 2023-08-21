from typing import Iterable, Optional

from environment.entities import (
    EnvironmentStatus,
    EnvironmentType,
    Region,
    ResearchEnvironment,
    ResearchWorkspace,
    EntityScaffolding,
    Workflow,
    WorkflowStatus,
)
from django.apps import apps


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
    workbenches: dict, gcp_project_id: str, region: Region, projects: Iterable[PublishedProject]
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
            project=_get_project_for_environment(workbench["dataset_identifier"], projects),
            gpu_accelerator_type=workbench.get("gpu_accelerator_type"),
            workflow_in_progress=deserialize_workflow_details(workbench.get("workflow_in_progress")),
        )
        if workbench.get("type") == "Workbench"
        else deserialize_entity_scaffolding(workbench)
        for workbench in workbenches
    ]


def deserialize_workflow_details(workflow_data: dict) -> Optional[Workflow]:
    if not workflow_data:
        return None
    return Workflow(
        id=workflow_data["id"],
        build_type=workflow_data["build_type"],
        status=WorkflowStatus(workflow_data["status"]),
        error_information=workflow_data["error"]
    )


def deserialize_workspace_details(data: dict, projects: Iterable[PublishedProject]) -> ResearchWorkspace:
    return ResearchWorkspace(
        region=Region(data["region"]),
        gcp_project_id=data["gcp_project_id"],
        gcp_billing_id=data["billing_info"]["billing_account_id"],
        workbenches=deserialize_research_environments(
            data["workbenches"], data["gcp_project_id"], Region(data["region"]), projects
        ),
    )


def deserialize_entity_scaffolding(data: dict) -> EntityScaffolding:
    return EntityScaffolding(gcp_project_id=data["gcp_project_id"])


def deserialize_workspaces(data: dict, projects: Iterable[PublishedProject]) -> Iterable[ResearchWorkspace]:
    return [
        deserialize_workspace_details(workspace_data, projects)
        if workspace_data.get("type") == "Workspace"
        else deserialize_entity_scaffolding(workspace_data)
        for workspace_data in data
    ]


def _get_project_for_environment(
    dataset_identifier: str,
    projects: Iterable[PublishedProject],
) -> PublishedProject:
    return next(iter([
        project
        for project in projects
        if _project_data_group(project) == dataset_identifier
    ]))
