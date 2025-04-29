from dataclasses import asdict
from typing import Iterable, Union
from django.forms.models import model_to_dict
from django.contrib.auth import get_user_model

from environment.entities import (
    ResearchWorkspace,
    ResearchEnvironment,
    EntityScaffolding,
    SharedWorkspace,
)

User = get_user_model()


def serialize_workspaces(
    workspaces: Iterable[Union[ResearchWorkspace, EntityScaffolding]]
):
    return [
        serialize_workspace_details(research_workspace)
        if isinstance(research_workspace, ResearchWorkspace)
        else serialize_entity_scaffolding(research_workspace)
        for research_workspace in workspaces
    ]


def serialize_workspace_details(workspace: ResearchWorkspace):
    return {
        "region": workspace.region.value,
        "gcp_project_id": workspace.gcp_project_id,
        "gcp_billing_id": workspace.gcp_billing_id,
        "status": workspace.status.value,
        "workbenches": [
            serialize_workbench(wb)
            if isinstance(wb, ResearchEnvironment)
            else serialize_entity_scaffolding(wb)
            for wb in workspace.workbenches
        ],
    }


def serialize_workbench(workbench: ResearchEnvironment):
    return {
        "gcp_identifier": workbench.gcp_identifier,
        "dataset_identifier": workbench.dataset_identifier,
        "url": workbench.url,
        "workspace_name": workbench.workspace_name,
        "status": workbench.status.value,
        "is_running": workbench.is_running,
        "cpu": workbench.cpu,
        "memory": workbench.memory,
        "region": workbench.region.value,
        "type": workbench.type.value,
        "project": model_to_dict(
            workbench.project, fields=["pk", "slug", "title", "version"]
        ),
        "machine_type": workbench.machine_type,
        "disk_size": workbench.disk_size,
        "gpu_accelerator_type": workbench.gpu_accelerator_type,
    }


def serialize_entity_scaffolding(entity_scaffolding: EntityScaffolding):
    return {
        "gcp_project_id": entity_scaffolding.gcp_project_id,
        "status": entity_scaffolding.status.value,
    }


def serialize_shared_workspaces(shared_workspaces: Iterable[SharedWorkspace]):
    return [
        serialize_shared_workspace_details(shared_workspace)
        for shared_workspace in shared_workspaces
    ]


def serialize_shared_workspace_details(shared_workspace: SharedWorkspace):
    return {
        "gcp_project_id": shared_workspace.gcp_project_id,
        "gcp_billing_id": shared_workspace.gcp_billing_id,
        "is_owner": shared_workspace.is_owner,
        "status": shared_workspace.status.value,
        "buckets": [asdict(bucket) for bucket in shared_workspace.buckets],
    }


def serialize_user(user: User):
    return model_to_dict(user, fields=["id", "username"])
