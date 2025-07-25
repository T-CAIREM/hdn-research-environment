from dataclasses import asdict
from typing import Iterable, Dict
from django.forms.models import model_to_dict
from django.contrib.auth import get_user_model


from environment.entities import ResearchWorkspace, SharedWorkspace, SharedBucketObject
from environment.models import (
    VMInstance,
    BucketSharingInvite,
    BillingAccountSharingInvite,
)

User = get_user_model()


def serialize_workspaces(workspaces: Iterable[ResearchWorkspace]):
    return [
        serialize_workspace_details(research_workspace)
        for research_workspace in workspaces
    ]


def serialize_workspace_details(workspace: ResearchWorkspace):
    return {
        "region": workspace.region.value,
        "gcp_project_id": workspace.gcp_project_id,
        "gcp_billing_id": workspace.gcp_billing_id,
        "status": workspace.status.value,
        "workbenches": [serialize_workbench(wb) for wb in workspace.workbenches],
    }


def serialize_workbench(workbench):
    return {
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


def serialize_vm_instances(vm_instances: Iterable[VMInstance]):
    return [
        {
            **model_to_dict(vm),
            "name": vm.get_instance_value(),
            "region": vm.region.region,
            "gpu_accelerators": [
                model_to_dict(gpu) for gpu in vm.gpu_accelerators.all()
            ],
        }
        for vm in vm_instances
    ]


def serialize_projects(projects):
    return [
        model_to_dict(project, fields=["id", "slug", "version"]) for project in projects
    ]


def serialize_bucket_sharing_invitations(
    bucket_sharing_invitations: Iterable[BucketSharingInvite],
):
    return [
        model_to_dict(
            bucket_sharing_invitation,
            fields=[
                "id",
                "user_contact_email",
                "is_consumed",
                "is_revoked",
                "permissions",
                "owner",
                "user",
            ],
        )
        for bucket_sharing_invitation in bucket_sharing_invitations
    ]


def serialize_billing_sharing_invitations(
    billing_sharing_invitations: Iterable[BillingAccountSharingInvite],
):
    return [
        model_to_dict(
            billing_sharing_invitation,
            fields=[
                "id",
                "user_contact_email",
                "is_consumed",
                "is_revoked",
                "billing_account_id",
                "owner",
                "user",
            ],
        )
        for billing_sharing_invitation in billing_sharing_invitations
    ]


def serialize_shared_bucket_objects(
    objects: Iterable[SharedBucketObject],
) -> list[Dict]:
    return [
        {
            "type": obj.type,
            "name": obj.name,
            "size": obj.size,
            "modification_time": obj.modification_time,
            "full_path": obj.full_path,
        }
        for obj in objects
    ]
