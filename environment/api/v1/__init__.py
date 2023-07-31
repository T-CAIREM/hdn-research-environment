from typing import Optional
from requests import Request

from environment.api.v1.decorators import api_request


@api_request
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


@api_request
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
