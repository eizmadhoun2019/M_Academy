"""Hub membership webhooks — ``docs/hub-contract.md`` §4.

The endpoint is deliberately outside ``/api/v1``: it is a machine route the proxy must never
forward browser traffic to. Every answer uses compact JSON, as the contract specifies, rather
than the API error envelope.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from academy.access.principals import ROLES
from academy.hub.assertions import WEBHOOK_CLAIMS, InvalidAssertion, verify
from academy.hub.cache import invalidate_directory
from academy.membership import member_deactivated
from academy.models import HubWebhookEvent

EVENT_TYPES = ("member_changed", "member_deactivated")
MAX_REF_LENGTH = 64
MAX_DEPARTMENT_REFS = 50


def _error(code: str, status: int) -> JsonResponse:
    return JsonResponse({"code": code}, status=status)


def _target(request: HttpRequest) -> str:
    query = request.META.get("QUERY_STRING", "")
    return f"{request.path_info}?{query}" if query else request.path_info


def _token(request: HttpRequest) -> str:
    name = str(settings.ACADEMY_HUB_WEBHOOK_HEADER)
    return str(request.META.get("HTTP_" + name.upper().replace("-", "_"), ""))


def _parse(body: bytes) -> dict[str, Any]:
    try:
        event = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"body is not JSON ({error})") from error
    if not isinstance(event, dict):
        raise ValueError("body must be a JSON object")

    try:
        UUID(str(event.get("event_id")))
    except (TypeError, ValueError) as error:
        raise ValueError("event_id must be a UUID") from error
    if event.get("type") not in EVENT_TYPES:
        raise ValueError(f"type must be one of {', '.join(EVENT_TYPES)}")
    try:
        UUID(str(event.get("organization_id")))
    except (TypeError, ValueError) as error:
        raise ValueError("organization_id must be a UUID") from error
    user_ref = event.get("user_ref")
    if not isinstance(user_ref, str) or not user_ref or len(user_ref) > MAX_REF_LENGTH:
        raise ValueError("user_ref must be a reference of at most 64 characters")
    occurred_at = event.get("occurred_at")
    if isinstance(occurred_at, bool) or not isinstance(occurred_at, int):
        raise ValueError("occurred_at must be integer Unix seconds")
    refs = event.get("department_refs", [])
    if not isinstance(refs, list) or len(refs) > MAX_DEPARTMENT_REFS:
        raise ValueError("department_refs must be a list of at most 50 references")
    if any(not isinstance(ref, str) or not ref or len(ref) > MAX_REF_LENGTH for ref in refs):
        raise ValueError("department references must be 1-64 characters")
    if "role" in event and event["role"] not in ROLES:
        raise ValueError("role must be platform_admin, department_manager or employee")
    if "is_active" in event and not isinstance(event["is_active"], bool):
        raise ValueError("is_active must be a boolean")
    return event


@csrf_exempt
def hub_webhook(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    return _post(request)


def _post(request: HttpRequest) -> HttpResponse:
    limit = int(getattr(settings, "ACADEMY_API_BODY_LIMIT_BYTES", 2 * 1024 * 1024))
    if len(request.body) > limit:
        return _error("payload_too_large", 413)

    token = _token(request)
    if not token:
        return _error("unauthorized", 401)
    try:
        claims = verify(
            token,
            keys=settings.ACADEMY_HUB_WEBHOOK_KEYS,
            issuer=settings.ACADEMY_HUB_ISSUER,
            audience=f"{settings.ACADEMY_HUB_AUDIENCE}:webhooks",
            lifetime=settings.ACADEMY_HUB_WEBHOOK_TTL,
            skew=settings.ACADEMY_HUB_CLOCK_SKEW,
            method=request.method,
            target=_target(request),
            required_claims=WEBHOOK_CLAIMS,
        )
    except InvalidAssertion:
        return _error("unauthorized", 401)

    body = request.body
    digest = hashlib.sha256(body).hexdigest()
    if claims.get("body_sha256") != digest:
        return _error("unauthorized", 401)

    try:
        event = _parse(body)
    except ValueError:
        return _error("validation_error", 400)

    organization_id = UUID(str(event["organization_id"]))
    if organization_id != UUID(str(settings.ACADEMY_ORGANIZATION_ID)):
        return _error("forbidden", 403)

    duplicate = _accept(organization_id, event, digest)
    if duplicate is None:
        return _error("idempotency_conflict", 409)
    return JsonResponse({"accepted": True, "duplicate": duplicate})


def _accept(organization_id: UUID, event: dict[str, Any], digest: str) -> bool | None:
    """Record the receipt and apply the event in one transaction.

    Returns ``True`` for a duplicate with the same body, ``False`` for a first delivery, and
    ``None`` when the event id was reused for different content.
    """
    event_id = UUID(str(event["event_id"]))
    try:
        with transaction.atomic():
            HubWebhookEvent.objects.create(
                organization_id=organization_id,
                event_id=event_id,
                event_type=str(event["type"]),
                user_ref=str(event["user_ref"]),
                body_sha256=digest,
            )
            invalidate_directory(organization_id)
            if event["type"] == "member_deactivated":
                member_deactivated(organization_id, str(event["user_ref"]))
        return False
    except IntegrityError:
        existing = HubWebhookEvent.objects.filter(
            organization_id=organization_id, event_id=event_id
        ).first()
        if existing is None:
            return None
        return True if existing.body_sha256 == digest else None
