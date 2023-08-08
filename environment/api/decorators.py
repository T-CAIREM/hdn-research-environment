from functools import wraps
from typing import Callable

import google.oauth2.id_token
from django.conf import settings
from requests import Request, Response, Session


def _apply_api_credentials(request: Request, audience: str):
    auth_request = google.auth.transport.requests.Request()
    id_token = google.oauth2.id_token.fetch_id_token(auth_request, audience)

    request.headers["Authorization"] = f"Bearer {id_token}"


def api_request(
    request_creator_callable: Callable[..., Request],
) -> Callable:
    api_url = settings.CLOUD_RESEARCH_ENVIRONMENTS_API_URL

    @wraps(request_creator_callable)
    def wrapper(*args, **kwargs) -> Response:
        session = Session()
        request = request_creator_callable(*args, **kwargs)
        request.url = f"{api_url}{request.url}"
        prepped = request.prepare()
        _apply_api_credentials(prepped, api_url)

        return session.send(prepped)

    return wrapper
