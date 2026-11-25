"""Resolve the caller's access once per request and refuse a suspended account's pages."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, cast

from django.http import HttpRequest, HttpResponseBase
from django.shortcuts import render

from academy.access.cache import cached_access
from academy.access.principals import current_principal
from academy.access.suspensions import is_suspended
from academy.authorization.core import Access

#: Pages that must stay reachable while an account is blocked.
_ALLOWED_PATHS = (
    "/academy/login/",
    "/academy/logout/",
    "/academy/access-denied/",
)


class AcademyAccessMiddleware:
    """Attach ``request.academy_access``; the API and the pages share this one decision."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        access: Access | None = None
        principal = current_principal(request)
        if principal is not None:
            if is_suspended(principal.organization_id, principal.user_ref):
                principal = replace(principal, suspended=True)
            access = cached_access(principal)
            cast(Any, request).academy_access = access
            reason = access.denied_reason
            if reason is not None and _is_blocked_page(request):
                return render(
                    request,
                    "academy/access_denied.html",
                    {"reason": reason},
                    status=403,
                )
        return self.get_response(request)


def _is_blocked_page(request: HttpRequest) -> bool:
    path = request.path_info
    if not path.startswith("/academy/") or path.startswith("/academy/preview/"):
        return False
    return path not in _ALLOWED_PATHS
