"""Company invitations — ``docs/domain-model.md`` §2.0.9, T-027 CP2.

An invitation binds an address to one company, one department and a set of company role codes.
The raw token is mailed once and only its SHA-256 digest is stored, so a database read cannot
accept an invitation. Issuing a new invitation for the same address retires the previous token.

Acceptance creates (or reactivates) the account, verifies its address and creates (or restores)
its single membership. An address that already holds a membership in another company is refused
with ``already_member`` and no second row is written (D-043); an active member of the same
company is refused the same way, while a removed row is restored instead of duplicated.

The management endpoints (invite, resend, revoke) belong to the member-administration API of
T-028 CP3, which owns the ``academy.member.manage`` permission; this checkpoint ships the
service, the public acceptance endpoint and the mail.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote
from uuid import UUID

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from academy.access.accounts import validate_password_policy
from academy.access.tenancy import COMPANY_ROLES
from academy.access.tokens import digest
from academy.exceptions import (
    AlreadyMember,
    DomainValidationError,
    InvitationInvalid,
    NotFound,
)
from academy.models import Department, Invitation, Membership, Organization, User

logger = logging.getLogger("academy.security")


def _ttl_seconds() -> int:
    return int(getattr(settings, "ACADEMY_INVITATION_TTL_SECONDS", 604800))


def _link(raw: str) -> str:
    """Absolute link from the configured origin, never from a request's Host header."""
    origin = str(getattr(settings, "ACADEMY_PUBLIC_ORIGIN", "") or "").rstrip("/")
    return f"{origin}/academy/invite/?token={quote(raw)}"


def send_invitation_mail(invitation: Invitation, raw: str, company_name: str) -> None:
    """Render and send one invitation; a transport failure is logged, never raised."""
    body = render_to_string(
        "academy/mail/invitation.txt",
        {
            "email": invitation.email,
            "company_name": company_name,
            "link": _link(raw),
            "hours": max(1, _ttl_seconds() // 3600),
        },
    )
    try:
        send_mail(
            f"Join {company_name} on Masheed Academy",
            body,
            str(getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@masheed.local")),
            [invitation.email],
        )
    except Exception:
        logger.exception(
            "auth.invitation_mail_failed",
            extra={"event": "auth.invitation_mail_failed", "invitation_id": str(invitation.pk)},
        )


def invite(
    *,
    organization_id: UUID,
    email: str,
    roles: Any,
    department: Department | None = None,
    invited_by: Membership | None = None,
) -> tuple[Invitation, str]:
    """Issue one invitation and mail it; returns the row and the raw token exactly once."""
    address = str(email or "").strip().lower()
    if not address:
        raise DomainValidationError("the email is required", fields={"email": ["required"]})

    wanted = sorted({str(role).strip() for role in roles or () if str(role).strip()})
    unknown = [role for role in wanted if role not in COMPANY_ROLES]
    if not wanted:
        raise DomainValidationError("at least one role is required", fields={"roles": ["required"]})
    if unknown:
        raise DomainValidationError(
            "only company roles can be invited",
            fields={"roles": [f"unknown role: {role}" for role in unknown]},
        )

    account = User.objects.filter(email__iexact=address).first()
    if account is not None and Membership.objects.filter(user=account).exists():
        raise AlreadyMember("the email already belongs to a company")
    if department is not None and department.organization_id != organization_id:
        raise NotFound("department not found")

    raw = secrets.token_urlsafe(32)
    moment = timezone.now()
    with transaction.atomic():
        # One live invitation per address (docs/domain-model.md §2.0.9).
        Invitation.objects.for_org(organization_id).filter(
            email__iexact=address, accepted_at__isnull=True
        ).delete()
        invitation = Invitation.objects.create(
            organization_id=organization_id,
            email=address,
            token_hash=digest(raw),
            expires_at=moment + timedelta(seconds=_ttl_seconds()),
            invited_by=invited_by,
            department=department,
            roles=wanted,
        )

    organization = Organization.objects.filter(pk=organization_id).first()
    company_name = organization.name_ar if organization is not None else "Masheed Academy"
    send_invitation_mail(invitation, raw, company_name)
    logger.info(
        "auth.invitation_issued",
        extra={"event": "auth.invitation_issued", "invitation_id": str(invitation.pk)},
    )
    return invitation, raw


def revoke(*, organization_id: UUID, invitation_id: UUID) -> None:
    """Delete a pending invitation; the token stops working immediately."""
    deleted, _ = (
        Invitation.objects.for_org(organization_id)
        .filter(pk=invitation_id, accepted_at__isnull=True)
        .delete()
    )
    if not deleted:
        raise NotFound("invitation not found")


def accept(raw: str, *, password: str, display_name: str) -> Membership:
    """Accept an invitation once: create or reactivate the account and its membership."""
    name = str(display_name or "").strip()
    if not name:
        raise DomainValidationError(
            "the display name is required", fields={"display_name": ["required"]}
        )

    row = (
        Invitation.objects.select_related("department", "invited_by")
        .filter(token_hash=digest(str(raw or "")))
        .first()
    )
    moment = timezone.now()
    if row is None or row.accepted_at is not None or row.expires_at <= moment:
        raise InvitationInvalid("the invitation is invalid or has expired")

    account = User.objects.filter(email__iexact=row.email).first()
    restored = None
    if account is not None:
        if (
            Membership.objects.filter(user=account)
            .exclude(organization_id=row.organization_id)
            .exists()
        ):
            raise AlreadyMember("the email already belongs to another company")
        restored = Membership.objects.filter(
            user=account, organization_id=row.organization_id
        ).first()
        if restored is not None and restored.status != Membership.Status.REMOVED:
            raise AlreadyMember("the email already belongs to this company")

    with transaction.atomic():
        claimed = Invitation.objects.filter(pk=row.pk, accepted_at__isnull=True).update(
            accepted_at=moment
        )
        if claimed != 1:
            raise InvitationInvalid("the invitation is invalid or has expired")

        if account is None:
            account = User(
                email=row.email,
                display_name=name,
                status=User.Status.ACTIVE,
                is_email_verified=True,
            )
            validate_password_policy(account, password)
            account.set_password(password)
            account.password_changed_at = moment
            account.save()
        else:
            account = _activate_existing(account, password, moment)

        inviter = row.invited_by.user if row.invited_by is not None else None
        if restored is None:
            membership = Membership.objects.create(
                organization_id=row.organization_id,
                user=account,
                status=Membership.Status.ACTIVE,
                joined_at=moment,
                invited_by=inviter,
                department=row.department,
                roles=list(row.roles or []),
            )
        else:
            restored.status = Membership.Status.ACTIVE
            restored.joined_at = moment
            restored.removed_at = None
            restored.invited_by = inviter
            restored.department = row.department
            restored.roles = list(row.roles or [])
            restored.save(
                update_fields=[
                    "status",
                    "joined_at",
                    "removed_at",
                    "invited_by",
                    "department",
                    "roles",
                    "updated_at",
                ]
            )
            membership = restored

    logger.info(
        "auth.invitation_accepted",
        extra={
            "event": "auth.invitation_accepted",
            "invitation_id": str(row.pk),
            "user_id": str(account.pk),
        },
    )
    return membership


def _activate_existing(account: User, password: str, moment: datetime) -> User:
    """Verify an existing account and give it a password only when it has none."""
    fields: list[str] = []
    if not account.has_usable_password():
        validate_password_policy(account, password)
        account.set_password(password)
        account.password_changed_at = moment
        fields.extend(["password", "password_changed_at"])
    if not account.is_email_verified:
        account.is_email_verified = True
        fields.append("is_email_verified")
    if account.status == User.Status.UNVERIFIED:
        account.status = User.Status.ACTIVE
        fields.append("status")
    if fields:
        account.save(update_fields=[*fields, "updated_at"])
    return account
