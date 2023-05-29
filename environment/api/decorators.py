from typing import Callable
from functools import wraps, partial
from requests import Request, Response, Session

from django.conf import settings

from environment.api.auth import apply_api_v1_credentials, apply_api_v2_credentials


def api_request(
    credentials_application_callable: Callable[[Request], None],
    api_url: str,
    request_creator_callable: Callable[..., Request],
) -> Callable:
    @wraps(request_creator_callable)
    def wrapper(*args, **kwargs) -> Response:
        session = Session()
        request = request_creator_callable(*args, **kwargs)
        request.url = f"{api_url}{request.url}"
        prepped = request.prepare()
        credentials_application_callable(prepped)
        return session.send(prepped)

    return wrapper


api_v1_request = partial(
    api_request,
    apply_api_v1_credentials,
    settings.CLOUD_RESEARCH_ENVIRONMENTS_API_V1_URL,
)

api_v2_request = partial(
    api_request,
    apply_api_v2_credentials,
    settings.CLOUD_RESEARCH_ENVIRONMENTS_API_V2_URL,
)
