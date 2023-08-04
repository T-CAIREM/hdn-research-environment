from requests import Request
from typing import Optional

from environment.api.v2.decorators import api_request


@api_request
def create_cloud_identity(
    gcp_user_id: str,
    given_name: str,
    family_name: str,
    password: str,
    recovery_email: str,
) -> Request:
    json = {
        "user_name": gcp_user_id,
        "password": password,
        "given_name": given_name,
        "family_name": family_name,
        "recovery_email": recovery_email,
    }
    return Request("POST", url="/identity/create", json=json)


@api_request
def list_billing_accounts(email: str) -> Request:
    return Request("GET", url=f"/billing/{email}")


@api_request
def share_billing_account(
    owner_email: str,
    user_email: str,
    billing_account_id: str,
) -> Request:
    json = {
        "owner_email": owner_email,
        "user_email": user_email,
        "billing_account_id": billing_account_id,
    }
    return Request("POST", url="/billing/share", json=json)


@api_request
def revoke_billing_account_access(
    owner_email: str,
    user_email: str,
    billing_account_id: str,
) -> Request:
    json = {
        "owner_email": owner_email,
        "user_email": user_email,
        "billing_account_id": billing_account_id,
    }
    return Request("POST", url="/billing/revoke_access", json=json)


@api_request
def create_workspace(email: str, billing_account_id: str, region: str) -> Request:
    json = {
        "user_email": email,
        "billing_account_id": billing_account_id,
        "region": region,
    }
    return Request("POST", url="/workspace/create", json=json)


@api_request
def delete_workspace(
    email: str, billing_account_id: str, region: str, gcp_project_id: str
) -> Request:
    json = {
        "user_email": email,
        "billing_account_id": billing_account_id,
        "region": region,
        "workspace_project_id": gcp_project_id,
    }
    return Request("DELETE", url=f"/workspace/delete", json=json)


@api_request
def get_workspace_list(email: str) -> Request:
    return Request("GET", url=f"/workspace/{email}")


@api_request
def create_workbench(
    user_email: str,
    workbench_type: str,
    machine_type: str,
    region: str,
    dataset_identifier: str,
    persistent_disk: str,
    bucket_name: str,
    workspace_project_id: str,
    gpu_accelerator_type: Optional[str] = None,
):
    json = {
        "workbench_type": workbench_type,
        "machine_type": machine_type,
        "workspace_project_id": workspace_project_id,
        "dataset_identifier": dataset_identifier,
        "user_email": user_email,
        "bucket_name": bucket_name,
        "region": region,
        "persistent_disk": persistent_disk,
        "gpu_accelerator_type": gpu_accelerator_type,
    }

    return Request("POST", url="/workbench/create", json=json)


@api_request
def stop_workbench(
    workbench_type: str,
    workbench_resource_id: str,
    user_email: str,
    workspace_project_id: str,
) -> Request:
    json = {
        "workbench_type": workbench_type,
        "workspace_project_id": workspace_project_id,
        "user_email": user_email,
        "workbench_resource_id": workbench_resource_id,
    }
    return Request("POST", url="/workbench/stop", json=json)


@api_request
def start_workbench(
    workbench_type: str,
    workbench_resource_id: str,
    user_email: str,
    workspace_project_id: str,
) -> Request:
    json = {
        "workbench_type": workbench_type,
        "workspace_project_id": workspace_project_id,
        "user_email": user_email,
        "workbench_resource_id": workbench_resource_id,
    }
    return Request("POST", url="/workbench/start", json=json)


@api_request
def change_workbench_instance_type(
    workbench_type: str,
    machine_type: str,
    dataset_identifier: str,
    user_email: str,
    bucket_name: str,
    region: str,
    persistent_disk: str,
    workspace_project_id: str,
    workbench_resource_id: str,
    gpu_accelerator_type: Optional[str] = None,
) -> Request:
    json = {
        "workbench_type": workbench_type,
        "machine_type": machine_type,
        "workspace_project_id": workspace_project_id,
        "dataset_identifier": dataset_identifier,
        "user_email": user_email,
        "bucket_name": bucket_name,
        "region": region,
        "persistent_disk": persistent_disk,
        "gpu_accelerator_type": gpu_accelerator_type,
        "workbench_resource_id": workbench_resource_id,
    }
    return Request("POST", url="/workbench/update", json=json)


@api_request
def delete_workbench(
    environment_type: str,
    instance_type: str,
    dataset_identifier: str,
    gcp_user_email_id: str,
    bucket_name: str,
    region: str,
    persistent_disk: str,
    gcp_project_id: str,
    workbench_resource_id: str,
    gpu_accelerator_type: Optional[str] = None,
) -> Request:
    json = {
        "workbench_type": environment_type,
        "machine_type": instance_type,
        "workspace_project_id": gcp_project_id,
        "dataset_identifier": dataset_identifier,
        "user_email": gcp_user_email_id,
        "bucket_name": bucket_name,
        "region": region,
        "persistent_disk": persistent_disk,
        "gpu_accelerator_type": gpu_accelerator_type,
        "workbench_resource_id": workbench_resource_id,
    }
    return Request("DESTROY", url="/workbench/destroy", json=json)
