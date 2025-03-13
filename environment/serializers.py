from typing import Iterable
from dataclasses import asdict
import json
from django.forms.models import model_to_dict
from django.core.serializers.json import DjangoJSONEncoder


from environment.entities import ResearchWorkspace


def serialize_workspaces(workspaces: Iterable[ResearchWorkspace]):
    return [
        serialize_workspace_details(research_workspace)
        for research_workspace in workspaces
    ]


def serialize_workspace_details(workspace: ResearchWorkspace):
    return json.dumps(
        {
            "region": workspace.region.value,
            "gcp_project_id": workspace.gcp_project_id,
            "gcp_billing_id": workspace.gcp_billing_id,
            "status": workspace.status.value,
            "workbenches": [serialize_workbench(wb) for wb in workspace.workbenches],
        }
    )


def serialize_workbench(workbench):
    return json.dumps(
        {
            "gcp_identifier": workbench.gcp_identifier,
            "dataset_identifier": workbench.dataset_identifier,
            "url": workbench.url,
            "workspace_name": workbench.workspace_name,
            "status": workbench.status.value,
            "cpu": workbench.cpu,
            "memory": workbench.memory,
            "region": workbench.region.value,
            "type": workbench.type.value,
            "project": model_to_dict(workbench.project, fields=["pk", "slug"]),
            "machine_type": workbench.machine_type,
            "disk_size": workbench.disk_size,
            "gpu_accelerator_type": workbench.gpu_accelerator_type,
        },
        cls=DjangoJSONEncoder,
    )
