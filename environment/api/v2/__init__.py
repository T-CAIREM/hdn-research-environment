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
        "email": email,
        "billing_account_id": billing_account_id,
        "region": region,
    }
    return Request("POST", url="/workspace/create", json=json)


@api_request
def delete_workspace(email: str, gcp_project_id: str) -> Request:
    return Request("DELETE", url=f"/workspace/{email}/{gcp_project_id}")


@api_request
def get_workspace_list(email: str) -> Request:
    return Request("GET", url=f"/workspace/{email}")



@api_request
def create_workbench(
    invoker_username: str,
    gcp_user_email_id: str,
    environment_type: str,
    instance_type: str,
    region: str,
    group_granting_data_access: str,
    persistent_disk: str,
    bucket_name: str,
    gcp_project_id: str,
    gpu_accelerator: Optional[str] = None,
):
    json = {
        "invoker_username": invoker_username,
        "workbench_type": environment_type,
        "machine_type": instance_type,
        "user_project_id": gcp_project_id,
        "dataset": group_granting_data_access,
        "email_id": gcp_user_email_id,
        "bucket_name": bucket_name,
        "region": region,
        "persistent_disk": persistent_disk,
        "gpu_accelerator": gpu_accelerator,
    }

    return Request("POST", url="/workbench/create", json=json)


@api_request
def stop_workbench(
    invoker_username: str, instance_name: str, workbench_id: str, gcp_project_id: str
) -> Request:
    params = {
        "invoker_username": invoker_username,
        "instance_name": instance_name,
        "gcp_workbench_identifier": workbench_id,
        "user_project": gcp_project_id,
    }
    return Request("PUT", url="/workbench/stop", params=params)
