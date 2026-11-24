"""HTTP adapters for :mod:`academy.authorization.core`.

Both adapters read the access already resolved for the request (``request.academy_access``),
set once by the authentication layer in T-014/T-015. They contain no policy of their own; that
is what keeps the API and the server-rendered pages on one decision path.
"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponseBase
from rest_framework.permissions import BasePermission

from academy.authorization.core import Access, Capability
from academy.exceptions import Forbidden


def _access_of(request: Any) -> Access:
    access = getattr(request, "academy_access", None)
    if not isinstance(access, Access):
        raise Forbidden("the request has no resolved Academy access")
    return access


class AcademyPermission(BasePermission):
    """DRF permission: the view declares ``academy_capability`` (or the class does)."""

    capability: Capability | str | None = None

    def has_permission(self, request: Any, view: Any) -> bool:
        capability = self.capability or getattr(view, "academy_capability", None)
        if capability is None:
            return False
        access = getattr(request, "academy_access", None)
        return isinstance(access, Access) and access.allows(capability)


class CapabilityRequiredMixin:
    """Web view mixin: deny before the view body runs, with the documented domain error."""

    academy_capability: Capability | str

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        _access_of(request).require(self.academy_capability)
        return super().dispatch(request, *args, **kwargs)  # type: ignore[misc]
