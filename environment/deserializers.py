from typing import Iterable

from environment.entities import (
    EnvironmentStatus,
    EnvironmentType,
    Region,
    ResearchEnvironment,
    ResearchWorkspace,
    EntityScaffolding,
)


def deserialize_research_environments(
    workbenches: dict, gcp_project_id: str, region: Region
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
            type=EnvironmentType(workbench["type"]),
            machine_type=workbench["machine_type"],
            disk_size=workbench.get("disk_size"),
            gpu_accelerator_type=workbench.get("gpu_accelerator_type"),
            workflow_in_progress=workbench.get("workflow_in_progress"),
        )
        if workbench.get("type") == "Workbench"
        else deserialize_entity_scaffolding(workbench)
        for workbench in workbenches
    ]


def deserialize_workspace_details(data: dict) -> ResearchWorkspace:
    return ResearchWorkspace(
        region=Region(data["region"]),
        gcp_project_id=data["gcp_project_id"],
        gcp_billing_id=data["billing_account_id"],
        workbenches=deserialize_research_environments(
            data["workbenches"], data["gcp_project_id"], Region(data["region"])
        ),
    )


def deserialize_entity_scaffolding(data: dict) -> EntityScaffolding:
    return EntityScaffolding(gcp_project_id=data["gcp_project_id"])


def deserialize_workspaces(data: dict) -> Iterable[ResearchWorkspace]:
    return [
        deserialize_workspace_details(workspace_data)
        if data.get("type") == "Workspace"
        else deserialize_entity_scaffolding(workspace_data)
        for workspace_data in data
    ]
