from typing import Callable

import google.auth.jwt as jwt
from django.conf import settings
from requests import Request


def _credentials_apply_closure(
    jwt_path: str, jwt_audience: str
) -> Callable[[Request], None]:
    credentials = jwt.Credentials.from_service_account_file(
        jwt_path,
        audience=jwt_audience,
    )

    def apply_api_credentials(request: Request) -> None:
        credentials.before_request(None, request.method, request.url, request.headers)

    return apply_api_credentials


apply_api_v1_credentials = _credentials_apply_closure(
    jwt_path=settings.CLOUD_RESEARCH_ENVIRONMENTS_API_V1_JWT_SERVICE_ACCOUNT_PATH,
    jwt_audience=settings.CLOUD_RESEARCH_ENVIRONMENTS_API_V1_JWT_AUDIENCE,
)

apply_api_v2_credentials = _credentials_apply_closure(
    jwt_path=settings.CLOUD_RESEARCH_ENVIRONMENTS_API_V2_JWT_SERVICE_ACCOUNT_PATH,
    jwt_audience=settings.CLOUD_RESEARCH_ENVIRONMENTS_API_V2_JWT_AUDIENCE,
)
