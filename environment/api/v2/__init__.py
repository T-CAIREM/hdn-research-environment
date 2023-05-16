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


@api_v2_request
def list_billing_accounts(email: str) -> Request:
    json = {"email": email}
    return Request("POST", url="/billing/list", json=json)


@api_v2_request
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


@api_v2_request
def create_workspace(
    email: str, billing_account_id: str, region: str
) -> Request:
    json = {
        "email": email,
        "billing_account_id": billing_account_id,
        "region": region,
    }
    return Request("POST", url="/workspace/create", json=json)
