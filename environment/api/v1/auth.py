from typing import Callable

import google.auth.jwt as jwt
from django.conf import settings
from requests import Request


def _credentials_apply_closure() -> Callable[[Request], None]:
    credentials = jwt.Credentials.from_service_account_file(
        settings.CLOUD_RESEARCH_ENVIRONMENTS_API_V1_JWT_SERVICE_ACCOUNT_PATH,
        audience=settings.CLOUD_RESEARCH_ENVIRONMENTS_API_V1_JWT_AUDIENCE,
    )

    def apply_api_credentials(request: Request) -> None:
        credentials.before_request(None, request.method, request.url, request.headers)

    return apply_api_credentials


apply_api_credentials = _credentials_apply_closure()
