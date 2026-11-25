"""One error shape for the whole API — ``docs/api.md`` §1 and §11.

Domain failures carry a stable ``code`` already (``academy.exceptions``); this module maps it to
an HTTP status and wraps it as ``{code, detail, fields}``. DRF's own exceptions are translated
into the same shape, so a client never has to parse two formats.
"""

from __future__ import annotations

from typing import Any

from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from academy.exceptions import AcademyError

STATUS_BY_CODE = {
    "validation_error": status.HTTP_400_BAD_REQUEST,
    "upload_too_large": status.HTTP_400_BAD_REQUEST,
    "unsupported_type": status.HTTP_400_BAD_REQUEST,
    "progress_skip_rejected": status.HTTP_400_BAD_REQUEST,
    "unauthorized": status.HTTP_401_UNAUTHORIZED,
    "account_inactive": status.HTTP_403_FORBIDDEN,
    "access_suspended": status.HTTP_403_FORBIDDEN,
    "forbidden": status.HTTP_403_FORBIDDEN,
    "lesson_locked": status.HTTP_403_FORBIDDEN,
    "not_found": status.HTTP_404_NOT_FOUND,
    "method_not_allowed": status.HTTP_405_METHOD_NOT_ALLOWED,
    "idempotency_conflict": status.HTTP_409_CONFLICT,
    "upload_missing": status.HTTP_409_CONFLICT,
    "checksum_mismatch": status.HTTP_409_CONFLICT,
    "retry_limit_reached": status.HTTP_409_CONFLICT,
    "media_not_ready": status.HTTP_409_CONFLICT,
    "lesson_not_eligible": status.HTTP_409_CONFLICT,
    "enrollment_incomplete": status.HTTP_409_CONFLICT,
    "acknowledgment_not_required": status.HTTP_409_CONFLICT,
    "last_admin": status.HTTP_409_CONFLICT,
    "conflict": status.HTTP_409_CONFLICT,
    "course_published_locked": status.HTTP_409_CONFLICT,
    "draft_exists": status.HTTP_409_CONFLICT,
    "version_published": status.HTTP_409_CONFLICT,
    "position_mismatch": status.HTTP_409_CONFLICT,
    "publish_invalid": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "target_empty": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "throttled": status.HTTP_429_TOO_MANY_REQUESTS,
    "unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
}


def _payload(code: str, detail: str, fields: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "detail": detail, "fields": fields or {}}


def academy_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Translate Academy and DRF failures into the documented envelope."""
    if isinstance(exc, AcademyError):
        return Response(
            _payload(exc.code, exc.detail, exc.fields),
            status=STATUS_BY_CODE.get(exc.code, status.HTTP_400_BAD_REQUEST),
        )

    if isinstance(exc, Http404):
        return Response(_payload("not_found", "not found"), status=status.HTTP_404_NOT_FOUND)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    code = _code_for(exc)
    detail = str(getattr(exc, "detail", "")) or code
    fields: dict[str, Any] = {}
    if isinstance(exc, exceptions.ValidationError) and isinstance(exc.detail, dict):
        fields = {key: list(value) for key, value in exc.detail.items()}
    response.data = _payload(code, detail, fields)
    return response


def _code_for(exc: Exception) -> str:
    if isinstance(exc, exceptions.NotAuthenticated | exceptions.AuthenticationFailed):
        return "unauthorized"
    if isinstance(exc, exceptions.PermissionDenied):
        return "forbidden"
    if isinstance(exc, exceptions.NotFound):
        return "not_found"
    if isinstance(exc, exceptions.Throttled):
        return "throttled"
    if isinstance(exc, exceptions.MethodNotAllowed):
        return "method_not_allowed"
    if isinstance(exc, exceptions.ValidationError):
        return "validation_error"
    return "validation_error"
