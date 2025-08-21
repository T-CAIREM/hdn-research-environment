from dataclasses import asdict
from typing import Iterable, Dict, Union
from django.forms.models import model_to_dict
from django.contrib.auth import get_user_model


from environment.entities import (
    ResearchWorkspace,
    SharedWorkspace,
    SharedBucketObject,
    QuotaInfo,
    EntityScaffolding,
    ResearchEnvironment,
)
from environment.models import (
    VMInstance,
    BucketSharingInvite,
    BillingAccountSharingInvite,
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
        "project": model_to_dict(
            workbench.project, fields=["pk", "slug", "version", "title"]
        ),
        "machine_type": workbench.machine_type,
        "disk_size": workbench.disk_size,
        "gpu_accelerator_type": workbench.gpu_accelerator_type,
    }


def serialize_shared_workspaces(
    shared_workspaces: Iterable[Union[SharedWorkspace, EntityScaffolding]]
):
    return [
        serialize_shared_workspace_details(shared_workspace)
        if isinstance(shared_workspace, SharedWorkspace)
        else serialize_entity_scaffolding(shared_workspace)
        for shared_workspace in shared_workspaces
    ]


def serialize_entity_scaffolding(scaffolding: EntityScaffolding) -> Dict:
    return {
        "status": scaffolding.status.value,
        "gcp_project_id": scaffolding.gcp_project_id,
    }


def serialize_shared_workspace_details(shared_workspace: SharedWorkspace):
    return {
        "gcp_project_id": shared_workspace.gcp_project_id,
        "gcp_billing_id": shared_workspace.gcp_billing_id,
        "is_owner": shared_workspace.is_owner,
        "status": shared_workspace.status.value,
        "buckets": [asdict(bucket) for bucket in shared_workspace.buckets],
    }


def serialize_user(user: User):
    model_to_dict(user, fields=["id", "username"])
    return {
        "id": user.id,
        "username": user.username,
        "is_authenticated": user.is_authenticated,
        "can_view_admin_console": user.has_access_to_admin_console(),
        "can_view_events": user.has_perms(["view_event_menu"]),
        "is_admin": user.is_admin,
    }


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


def serialize_quotas(objects: Iterable[QuotaInfo]) -> list[Dict]:
    return [
        {
            "metric_name": obj.metric_name,
            "limit": obj.limit,
            "usage": obj.usage,
            "usage_percentage": obj.usage_percentage,
        }
        for obj in objects
    ]
