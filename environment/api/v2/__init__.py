from functools import partial

from requests import Request
from django.conf import settings

from environment.api.decorators import api_request


api_v2_request = partial(api_request, settings.CLOUD_RESEARCH_ENVIRONMENTS_API_V2_URL)


@api_v2_request
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
