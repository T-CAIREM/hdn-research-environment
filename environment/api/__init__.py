from typing import Optional

from requests import Request

from environment.api.decorators import api_request


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
    dataset_identifier: str,
    disk_size: str,
    bucket_name: str,
    workspace_project_id: str,
    gpu_accelerator_type: Optional[str] = None,
    sharing_bucket_identifiers: Optional[list[str]] = None,
):
    json = {
        "workbench_type": workbench_type,
        "machine_type": machine_type,
        "workspace_project_id": workspace_project_id,
        "dataset_identifier": dataset_identifier,
        "user_email": user_email,
        "bucket_name": bucket_name,
        "disk_size": disk_size,
        "gpu_accelerator_type": gpu_accelerator_type,
        "sharing_bucket_identifiers": sharing_bucket_identifiers,
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
    return Request("PUT", url="/workbench/stop", json=json)


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
    return Request("PUT", url="/workbench/start", json=json)


@api_request
def change_workbench_machine_type(
    workbench_type: str,
    machine_type: str,
    user_email: str,
    workspace_project_id: str,
    workbench_resource_id: str,
) -> Request:
    json = {
        "workbench_type": workbench_type,
        "workspace_project_id": workspace_project_id,
        "user_email": user_email,
        "workbench_resource_id": workbench_resource_id,
        "machine_type": machine_type,
    }
    return Request("PUT", url="/workbench/update", json=json)


@api_request
def delete_workbench(
    workbench_type: str,
    user_email: str,
    workspace_project_id: str,
    workbench_resource_id: str,
) -> Request:
    json = {
        "workbench_type": workbench_type,
        "workspace_project_id": workspace_project_id,
        "user_email": user_email,
        "workbench_resource_id": workbench_resource_id,
    }
    return Request("DELETE", url="/workbench/destroy", json=json)


@api_request
def get_workflow(workflow_id: str) -> Request:
    return Request("GET", url=f"/workflow/{workflow_id}")


@api_request
def create_shared_workspace(
    user_email: str,
    billing_account_id: str,
) -> Request:
    json = {
        "user_email": user_email,
        "billing_account_id": billing_account_id,
    }
    return Request("POST", url="/workspace/shared/create", json=json)


@api_request
def delete_shared_workspace(
    workspace_project_id: str, billing_account_id: str, user_email: str
) -> Request:
    json = {
        "user_email": user_email,
        "billing_account_id": billing_account_id,
        "workspace_project_id": workspace_project_id,
    }
    return Request("DELETE", url="/workspace/shared/delete", json=json)


@api_request
def get_shared_workspaces(
    email: str,
) -> Request:
    return Request("GET", url=f"/workspace/shared/{email}")


@api_request
def create_shared_bucket(
    region: str,
    workspace_project_id: str,
    user_defined_bucket_name: str,
    user_email: str,
) -> Request:
    json = {
        "region": region,
        "workspace_project_id": workspace_project_id,
        "user_defined_bucket_name": user_defined_bucket_name,
        "user_email": user_email,
    }
    return Request("POST", url="/sharing/bucket/create", json=json)


@api_request
def delete_shared_bucket(bucket_name: str) -> Request:
    json = {"bucket_name": bucket_name}
    return Request("DELETE", url="/sharing/bucket/delete", json=json)


@api_request
def share_bucket(
    owner_email: str, user_email: str, workspace_project_id: str, bucket_name: str, permissions: str
) -> Request:
    json = {
        "sharer_email": owner_email,
        "accessor_email": user_email,
        "bucket_name": bucket_name,
        "project_id": workspace_project_id,
        "permissions": permissions
    }
    return Request("POST", url="/sharing/bucket/share", json=json)


@api_request
def revoke_shared_bucket_access(
    owner_email: str, user_email: str, bucket_name: str
) -> Request:
    json = {
        "sharer_email": owner_email,
        "accessor_email": user_email,
        "bucket_name": bucket_name,
    }
    return Request("POST", url="/sharing/bucket/revoke_access", json=json)


@api_request
def generate_signed_url(
    filename: str, size: int, bucket_name: str, user_email: str
) -> Request:
    json = {
        "filename": filename,
        "size": size,
        "bucket_name": bucket_name,
        "user_email": user_email,
    }
    return Request("POST", url="/sharing/bucket/generate_signed_url", json=json)


@api_request
def get_shared_bucket_content(
    bucket_name: str, subdir: str, user_email: str
) -> Request:
    return Request(
        "GET",
        url=f"/sharing/{bucket_name}",
        params={"subdir": subdir, "user_email": user_email},
    )


@api_request
def create_shared_bucket_directory(
    bucket_name: str, parent_path: str, directory_name: str, user_email: str
) -> Request:
    json = {
        "directory_name": directory_name,
        "parent_path": parent_path,
        "bucket_name": bucket_name,
        "user_email": user_email,
    }
    return Request("POST", url="/sharing/bucket/content/create", json=json)


@api_request
def delete_shared_bucket_content(
    bucket_name: str, full_path: str, user_email: str
) -> Request:
    json = {
        "full_path": full_path,
        "bucket_name": bucket_name,
        "user_email": user_email,
    }
    return Request("DELETE", url="/sharing/bucket/content/delete", json=json)
