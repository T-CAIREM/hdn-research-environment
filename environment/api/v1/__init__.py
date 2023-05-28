from typing import Optional
from functools import partial
from requests import Request

from django.conf import settings

from environment.api.decorators import api_request


api_v1_request = partial(api_request, settings.CLOUD_RESEARCH_ENVIRONMENTS_API_V1_URL)


@api_v1_request
def create_cloud_identity(
    gcp_user_id: str,
    given_name: str,
    family_name: str,
    password: str,
    recovery_email: str,
) -> Request:
    json = {
        "userid": gcp_user_id,
        "givenName": given_name,
        "familyName": family_name,
        "password": password,
        "recoveryEmail": recovery_email,
    }
    return Request("POST", url="/user", json=json)


@api_v1_request
def get_user_info(gcp_user_id: str) -> Request:
    return Request("GET", url=f"/user/{gcp_user_id}")


@api_v1_request
def get_workspace_details(gcp_user_id: str, gcp_project_id: str) -> Request:
    return Request("GET", url=f"/workspace/{gcp_user_id}/{gcp_project_id}")


@api_v1_request
def get_workspace_list(gcp_user_id: str) -> Request:
    return Request("GET", url=f"/workspace/list/{gcp_user_id}")


@api_v1_request
def stop_workbench(
    gcp_user_id: str, workbench_id: str, region: str, gcp_project_id: str
) -> Request:
    params = {
        "userid": gcp_user_id,
        "id": workbench_id,
        "region": region,
        "gcp_project_id": gcp_project_id,
    }
    return Request("PUT", url="/workbench/stop", params=params)


@api_v1_request
def start_workbench(
    gcp_user_id: str, workbench_id: str, region: str, gcp_project_id: str
) -> Request:
    params = {
        "userid": gcp_user_id,
        "id": workbench_id,
        "region": region,
        "gcp_project_id": gcp_project_id,
    }
    return Request("PUT", url="/workbench/start", params=params)


@api_v1_request
def change_workbench_instance_type(
    gcp_user_id: str,
    workbench_id: str,
    region: str,
    new_instance_type: str,
    gcp_project_id: str,
) -> Request:
    params = {
        "userid": gcp_user_id,
        "id": workbench_id,
        "region": region,
        "gcp_project_id": gcp_project_id,
        "machinetype": new_instance_type,
    }
    return Request("PUT", url="/workbench/update", params=params)


@api_v1_request
def delete_workbench(
    gcp_user_id: str, workbench_id: str, region: str, gcp_project_id: str
) -> Request:
    params = {
        "userid": gcp_user_id,
        "id": workbench_id,
        "region": region,
        "gcp_project_id": gcp_project_id,
    }
    return Request("DELETE", url="/workbench", params=params)


@api_v1_request
def create_workbench(
    gcp_user_id: str,
    environment_type: str,
    instance_type: str,
    group_granting_data_access: str,
    persistent_disk: str,
    bucket_name: str,
    gcp_project_id: str,
    vm_image: Optional[str] = None,
    gpu_accelerator: Optional[str] = None,
):
    json = {
        "userid": gcp_user_id,
        "type": environment_type,
        "machinetype": instance_type,
        "group_granting_data_access": group_granting_data_access,
        "bucketname": bucket_name,
        "gcp_project_id": gcp_project_id,
        "persistentdisk": persistent_disk,
        "vmimage": vm_image,
        "gpu_accelerator": gpu_accelerator,
    }
    json_without_empty_values = {
        key: val for key, val in json.items() if val is not None
    }
    return Request("POST", url="/workbench", json=json_without_empty_values)
