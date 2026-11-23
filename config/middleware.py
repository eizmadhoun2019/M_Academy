"""Request-scoped middleware.

Only one concern lives here: giving every request an id that appears in its log lines and in
the response, so a support report can be traced to the lines it caused.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from config.logging import REQUEST_ID

REQUEST_ID_HEADER = "X-Request-ID"

# An inbound id is accepted only when it is short and made of safe characters: it is echoed to
# the client and written to logs, so it never carries arbitrary upstream content.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestIdMiddleware:
    """Attach a validated request id to the log context and to the response."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex

        token = REQUEST_ID.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            REQUEST_ID.reset(token)

        response[REQUEST_ID_HEADER] = request_id
        return response
