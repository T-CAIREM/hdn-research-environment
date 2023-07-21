from typing import Iterable

from environment.entities import (
    EnvironmentStatus,
    EnvironmentType,
    Region,
    ResearchEnvironment,
    ResearchWorkspace,
)


def deserialize_research_environments(data: dict) -> Iterable[ResearchEnvironment]:
    return [
        ResearchEnvironment(
            gcp_identifier=workbench["gcp_identifier"],
            dataset_identifier=workbench["dataset_identifier"],
            url=workbench.get("url"),
            workspace_name=workspace["gcp_project_id"],
            status=EnvironmentStatus(workbench["status"]),
            cpu=workbench["cpu"],
            memory=workbench["memory"],
            region=Region(workspace["region"]),
            type=EnvironmentType(workbench["type"]),
        )
        for workspace in data
        for workbench in workspace["workbenches"]
    ]


def deserialize_workspace_details(data: dict) -> ResearchWorkspace:
    return ResearchWorkspace(
        region=data["region"],
        gcp_project_id=data["gcp_project_id"],
        gcp_billing_id=data["billing_account_id"],
    )


def deserialize_workspaces(data: dict) -> Iterable[ResearchWorkspace]:
    return [deserialize_workspace_details(workspace_data) for workspace_data in data]
