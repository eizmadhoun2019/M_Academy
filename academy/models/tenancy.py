"""Identity and tenancy entities — ``docs/domain-model.md`` §2.0.1–§2.0.4 (T-026 CP1).

``Organization`` and ``User`` are global (``BaseModel``); ``Department`` and ``Membership`` are
tenant-owned (``TenantModel``). The schema is expanded before any read path changes, so the
existing opaque ``*_ref`` columns stay authoritative until the CP2 backfill; every new FK
column on an existing table is nullable for that reason.

Two database guarantees are deliberate:

* ``UNIQUE (user_id)`` on ``Membership`` (D-043) — an account belongs to at most one company,
  and the per-request company lookup is one indexed row.
* ``UNIQUE (organization_id, id)`` on ``Department`` and ``Membership`` — the parents a composite
  tenant FK points at, so a child row cannot name another company's department or member.
"""

from __future__ import annotations

import uuid
from typing import Any
from zoneinfo import ZoneInfo

from django.contrib.auth.hashers import check_password, is_password_usable, make_password
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from academy.models.base import TenantManager, TenantModel

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
NOT_BLANK = r"\S"


class BaseModel(models.Model):
    """Global row: an id and timestamps, no organization (§1.1)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(BaseModel):
    """One company (tenant). Archived, never hard-deleted while tenant rows exist."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    name_ar = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200, null=True, blank=True)  # noqa: DJ001 - NULL is semantic: "not translated", never ""
    slug = models.CharField(max_length=60, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    default_language = models.CharField(max_length=5, default="ar")
    timezone = models.CharField(max_length=64, default="Asia/Riyadh")
    reminder_hour = models.SmallIntegerField(default=8)
    sender_name = models.CharField(max_length=120, null=True, blank=True)  # noqa: DJ001 - NULL is semantic: fall back to the deployment sender
    settings = models.JSONField(default=dict, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(name_ar__regex=NOT_BLANK),
                name="organization_name_not_blank",
            ),
            models.CheckConstraint(
                condition=models.Q(slug__regex=SLUG_PATTERN),
                name="organization_slug_format",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["active", "suspended", "archived"]),
                name="organization_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(default_language__in=["ar", "en"]),
                name="organization_language_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(reminder_hour__gte=0) & models.Q(reminder_hour__lte=23),
                name="organization_reminder_hour_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="archived", archived_at__isnull=False)
                    | (~models.Q(status="archived") & models.Q(archived_at__isnull=True))
                ),
                name="organization_archived_stamped",
            ),
        ]
        indexes = [models.Index(fields=["status"], name="organization_status")]

    def __str__(self) -> str:
        return self.name_ar

    def clean(self) -> None:
        super().clean()
        try:
            ZoneInfo(self.timezone)
        except (KeyError, ValueError) as error:
            raise ValueError(f"unknown IANA timezone: {self.timezone!r}") from error


class User(BaseModel):
    """One global account; e-mail and password authenticate it (T-027 CP1).

    The model carries the small interface :func:`django.contrib.auth.authenticate` needs, but
    the session is Academy's own (``academy.access.principals``), so no ``AUTH_USER_MODEL``
    swap or ``django.contrib.auth.login`` is involved.
    """

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []
    # Django's auth checks read these; Academy never puts this row behind request.user, but the
    # model is still a valid ``AUTH_USER_MODEL`` for ``authenticate()`` and password validators.
    is_anonymous = False
    is_authenticated = True

    class Status(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        DEACTIVATED = "deactivated", "Deactivated"

    email = models.EmailField(max_length=254)
    display_name = models.CharField(max_length=150)
    # T-026 CP2: the opaque Hub/dev reference this account was imported from. Migration-only:
    # dropped at contract (M6) once no legacy column is read.
    legacy_ref = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001 - NULL is semantic: the account was created locally
    # T-026 CP2: an imported account with no e-mail keeps a non-deliverable placeholder address
    # and cannot sign in until a real one is set (docs/migration-h1.5.md §3).
    must_set_email = models.BooleanField(default=False)
    # Django's password column; T-027 replaces the empty placeholder with an unusable hash.
    password = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UNVERIFIED)
    is_email_verified = models.BooleanField(default=False)
    preferred_language = models.CharField(max_length=5, default="ar")
    last_login_at = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    anonymized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="user_email_unique_ci"),
            models.CheckConstraint(
                condition=models.Q(display_name__regex=NOT_BLANK),
                name="user_display_name_not_blank",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["unverified", "active", "suspended", "deactivated"]),
                name="user_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(preferred_language__in=["ar", "en"]),
                name="user_language_valid",
            ),
            models.UniqueConstraint(
                fields=["legacy_ref"],
                condition=models.Q(legacy_ref__isnull=False),
                name="user_legacy_ref_unique",
            ),
        ]
        indexes = [models.Index(fields=["status"], name="user_status")]

    def __str__(self) -> str:
        return self.display_name

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def is_active(self) -> bool:
        """Accounts that may authenticate; suspension/deactivation refuses the credential."""
        if self.anonymized_at is not None or self.must_set_email:
            return False
        return self.status in {User.Status.UNVERIFIED, User.Status.ACTIVE}

    def get_username(self) -> str:
        return self.email

    def natural_key(self) -> tuple[str]:
        return (self.email,)

    def has_usable_password(self) -> bool:
        return is_password_usable(self.password)

    def set_password(self, raw_password: str) -> None:
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)


class AccountToken(BaseModel):
    """One single-use, hashed account token — email verification or password reset (T-027 CP1).

    Only the SHA-256 digest is stored, so a database read cannot replay a mailed link; the raw
    token exists once, in the message. ``used_at`` makes consumption a single atomic update.
    """

    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "verify_email", "Verify email"
        RESET_PASSWORD = "reset_password", "Reset password"

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="account_tokens")
    purpose = models.CharField(max_length=24, choices=Purpose.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(purpose__in=["verify_email", "reset_password"]),
                name="account_token_purpose_valid",
            ),
        ]
        indexes = [models.Index(fields=["user", "purpose"], name="account_token_user_purpose")]

    def __str__(self) -> str:
        return f"{self.purpose} for {self.user_id}"


class Department(TenantModel):
    """A node of one company's department tree (depth limit is a service rule)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    name_ar = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200, null=True, blank=True)  # noqa: DJ001 - NULL is semantic: "not translated", never ""
    # T-026 CP2: the opaque ``department_ref`` this node was imported from, unique per company
    # so the backfill can resolve a ref idempotently. Migration-only (dropped at contract, M6).
    legacy_ref = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001 - NULL is semantic: a locally created department has no legacy ref
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    position = models.IntegerField(default=0)
    objects: TenantManager[Department] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization_id", "id"], name="department_org_id_unique"
            ),
            models.UniqueConstraint(
                fields=["organization_id", "parent", "name_ar"],
                name="department_sibling_name_unique",
                nulls_distinct=False,
            ),
            models.CheckConstraint(
                condition=~models.Q(parent=models.F("id")),
                name="department_parent_not_self",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["active", "archived"]),
                name="department_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(name_ar__regex=NOT_BLANK),
                name="department_name_not_blank",
            ),
            models.UniqueConstraint(
                fields=["organization_id", "legacy_ref"],
                condition=models.Q(legacy_ref__isnull=False),
                name="department_legacy_ref_unique",
            ),
        ]
        indexes = [models.Index(fields=["organization_id", "status"], name="department_org_status")]

    def __str__(self) -> str:
        return self.name_ar


class Membership(TenantModel):
    """One account's single company membership (D-043)."""

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        REMOVED = "removed", "Removed"

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="memberships")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.INVITED)
    joined_at = models.DateTimeField(null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    objects: TenantManager[Membership] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            # D-043: the authoritative one-company-per-account constraint.
            models.UniqueConstraint(fields=["user_id"], name="membership_one_company_per_user"),
            models.UniqueConstraint(
                fields=["organization_id", "id"], name="membership_org_id_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["invited", "active", "suspended", "removed"]),
                name="membership_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="removed", removed_at__isnull=False)
                    | (~models.Q(status="removed") & models.Q(removed_at__isnull=True))
                ),
                name="membership_removed_stamped",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="active") | models.Q(joined_at__isnull=False),
                name="membership_active_joined",
            ),
        ]
        indexes = [
            models.Index(fields=["organization_id", "status"], name="membership_org_status"),
            models.Index(
                fields=["organization_id", "department"], name="membership_org_department"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} @ {self.organization_id}"
