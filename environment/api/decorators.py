from functools import wraps
from typing import Callable

import google.oauth2.id_token
from django.conf import settings
from requests import Request, Response, Session

# Seconds to wait for the API to accept the connection and then to respond. A
# billing share retries policy conflicts for about 35 s at worst before it
# answers, so this leaves room for that and still frees a stuck caller. A
# timeout raises requests.exceptions.Timeout, which background tasks retry.
API_REQUEST_TIMEOUT_SECONDS = 60


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

        return session.send(prepped, timeout=API_REQUEST_TIMEOUT_SECONDS)

    return wrapper
