"""HTTP transport to the Hub service — ``docs/hub-contract.md`` §3.

Standard library only: Academy's host seam must not drag a provider SDK into the request path.
The transport carries the documented timeouts, one synchronous retry with backoff, no
redirect following, and a shared circuit that opens after the configured number of exhausted
transient calls.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings
from django.core.cache import cache

from academy.exceptions import Conflict

DEFAULT_PATHS = {
    "users": "/v1/academy/users",
    "departments": "/v1/academy/departments",
    "department_members": "/v1/academy/department-members",
    "manager": "/v1/academy/manager",
    "roles": "/v1/academy/roles",
    "role_members": "/v1/academy/role-members",
    "mail": "/v1/academy/mail",
    "activity": "/v1/academy/activity-log",
}

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
CIRCUIT_KEY = "macademy:hub:circuit"


class HubUnavailable(Exception):
    """The Hub service could not answer; the caller returns 503 and defers the operation."""


class HubRejected(Exception):
    """The Hub answered with a non-retryable client error."""

    def __init__(self, status: int, code: str = "") -> None:
        self.status = status
        self.code = code
        super().__init__(f"Hub rejected the request with {status} {code}".strip())


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirect)


def _circuit_open() -> bool:
    until = cache.get(CIRCUIT_KEY)
    return bool(until and float(until) > time.time())


def _record_failure() -> None:
    failures = cache.get(CIRCUIT_KEY + ":count", 0) or 0
    failures = int(failures) + 1
    if failures >= int(getattr(settings, "ACADEMY_HUB_CIRCUIT_FAILURES", 3)):
        cache.set(
            CIRCUIT_KEY,
            time.time() + int(getattr(settings, "ACADEMY_HUB_CIRCUIT_SECONDS", 30)),
            timeout=int(getattr(settings, "ACADEMY_HUB_CIRCUIT_SECONDS", 30)) + 1,
        )
        failures = 0
    cache.set(CIRCUIT_KEY + ":count", failures, timeout=300)


def _record_success() -> None:
    cache.delete(CIRCUIT_KEY + ":count")


class HubHttpClient:
    """Signed service calls with the contract's retry, timeout and circuit behavior."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        paths: dict[str, str] | None = None,
    ) -> None:
        self.base_url = str(base_url if base_url is not None else settings.ACADEMY_HUB_API_BASE_URL)
        self.token = str(token if token is not None else settings.ACADEMY_HUB_API_TOKEN)
        merged = dict(DEFAULT_PATHS)
        merged.update({str(key): str(value) for key, value in (paths or {}).items()})
        self.paths = merged
        self.retries = int(getattr(settings, "ACADEMY_HUB_API_RETRIES", 1))
        self.backoff = float(getattr(settings, "ACADEMY_HUB_RETRY_BACKOFF", 0.1))
        self.timeout = float(getattr(settings, "ACADEMY_HUB_CONNECT_TIMEOUT", 0.5)) + float(
            getattr(settings, "ACADEMY_HUB_READ_TIMEOUT", 1)
        )

    # --- plumbing -----------------------------------------------------------

    def _url(self, resource: str, params: dict[str, str] | list[tuple[str, str]] | None) -> str:
        path = self.paths.get(resource, resource if resource.startswith("/") else "")
        if not path:
            raise HubRejected(404, "unknown_resource")
        url = self.base_url.rstrip("/") + path
        if isinstance(params, list):
            pairs = [(key, value) for key, value in params if value != ""]
        else:
            pairs = [(key, value) for key, value in (params or {}).items() if value != ""]
        return f"{url}?{urllib.parse.urlencode(pairs)}" if pairs else url

    def _request(
        self, method: str, url: str, body: bytes | None, idempotency_key: str | None
    ) -> tuple[int, dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with _opener().open(request, timeout=self.timeout) as response:
                raw = response.read()
                return int(response.status), _json(raw)
        except urllib.error.HTTPError as error:
            raw = error.read()
            raise _StatusError(int(error.code), _json(raw, tolerant=True)) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise _TransportError(str(error)) from error

    def _call(
        self,
        method: str,
        resource: str,
        *,
        params: dict[str, str] | list[tuple[str, str]] | None = None,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if _circuit_open():
            raise HubUnavailable("the Hub circuit is open")
        url = self._url(resource, params)
        body = (
            json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                status, data = self._request(method, url, body, idempotency_key)
            except _StatusError as error:
                if error.status not in RETRYABLE_STATUS:
                    if error.status == 409:
                        raise Conflict("the Hub reported an idempotency conflict") from error
                    raise HubRejected(error.status, str(error.data.get("code", ""))) from error
                last = error
            except _TransportError as error:
                last = error
            else:
                _record_success()
                return data
            if attempt < self.retries:
                time.sleep(self.backoff)
        _record_failure()
        raise HubUnavailable(str(last) if last else "the Hub did not answer")

    # --- the seam's verbs ---------------------------------------------------

    def get(
        self, resource: str, params: dict[str, str] | list[tuple[str, str]] | None = None
    ) -> dict[str, Any]:
        return self._call("GET", resource, params=params)

    def post(
        self,
        resource: str,
        payload: dict[str, Any],
        idempotency_key: str,
        *,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        params = {"organization_id": organization_id} if organization_id else None
        return self._call(
            "POST", resource, params=params, payload=payload, idempotency_key=idempotency_key
        )


class _StatusError(Exception):
    def __init__(self, status: int, data: dict[str, Any]) -> None:
        self.status = status
        self.data = data
        super().__init__(f"HTTP {status}")


class _TransportError(Exception):
    pass


def _json(raw: bytes, *, tolerant: bool = False) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        if tolerant:
            return {}
        raise HubUnavailable("the Hub answered with a non-JSON body") from None
    return value if isinstance(value, dict) else {}
