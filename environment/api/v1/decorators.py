from typing import Callable
from functools import wraps
from requests import Request, Response, Session

from django.conf import settings

from environment.api.v1.auth import apply_api_credentials


def api_request(
    request_creator_callable: Callable[..., Request],
) -> Callable:
    api_url = settings.CLOUD_RESEARCH_ENVIRONMENTS_API_V1_URL

    @wraps(request_creator_callable)
    def wrapper(*args, **kwargs) -> Response:
        session = Session()
        request = request_creator_callable(*args, **kwargs)
        request.url = f"{api_url}{request.url}"
        prepped = request.prepare()
        apply_api_credentials(prepped)

        return session.send(prepped)

    return wrapper
