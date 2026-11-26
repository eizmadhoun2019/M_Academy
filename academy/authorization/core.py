"""Capability and scope resolution — ``CHARTER.md`` §3.1, D-027, D-028.

The layer is deliberately independent of HTTP and of the database: a caller builds a
:class:`Principal` from a verified identity, supplies the grants it has read (T-016 owns the
table and its service), and gets an immutable :class:`Access`. The DRF permission and the web
mixin in :mod:`academy.authorization.django` only translate a request into that call, so the
allow/deny/scope matrix is testable without a view.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from academy.exceptions import AccessSuspended, Forbidden, InactiveAccount

AUTHORIZATION_MODES = ("role_plus_grants", "grants_only")


class Capability(StrEnum):
    """The five capabilities of ``docs/api.md`` §2."""

    LEARN = "academy.learn"
    MANAGE_CONTENT = "academy.manage_content"
    ASSIGN = "academy.assign"
    VIEW_REPORTS = "academy.view_reports"
    ADMIN = "academy.admin"


MANAGEMENT_CAPABILITIES = frozenset(
    {
        Capability.MANAGE_CONTENT,
        Capability.ASSIGN,
        Capability.VIEW_REPORTS,
        Capability.ADMIN,
    }
)


@dataclass(frozen=True, slots=True)
class Scope:
    """Where a capability applies: every department, or an explicit set."""

    all_departments: bool = False
    departments: frozenset[str] = frozenset()

    @classmethod
    def everything(cls) -> Scope:
        return cls(all_departments=True)

    @classmethod
    def for_departments(cls, refs: Iterable[str]) -> Scope:
        return cls(departments=frozenset(ref for ref in refs if ref))

    def covers(self, department_ref: str | None) -> bool:
        """A personal capability covers ``None``; a departmental one needs its ref."""
        if self.all_departments:
            return True
        if department_ref is None:
            return False
        return department_ref in self.departments

    def __or__(self, other: Scope) -> Scope:
        if self.all_departments or other.all_departments:
            return Scope.everything()
        return Scope(departments=self.departments | other.departments)


@dataclass(frozen=True, slots=True)
class Principal:
    """A verified caller: identity metadata only, never a name or an e-mail (ADR-002)."""

    user_ref: str
    organization_id: UUID
    roles: frozenset[str] = frozenset()
    department_refs: frozenset[str] = frozenset()
    is_active: bool = True
    suspended: bool = False
    # T-026 CP3: the account and its single membership the company was derived from. They stay
    # ``None`` for a Hub claim, which carries only the signed identity (D-032, T-032).
    user_id: UUID | None = None
    membership_id: UUID | None = None

    @property
    def is_authenticated(self) -> bool:
        """DRF's ``IsAuthenticated`` reads this; identity itself is verified by T-014/T-015."""
        return True

    @property
    def is_anonymous(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Grant:
    """One stored Academy grant (``docs/domain-model.md`` §2.14), read by T-016."""

    capability: str
    scope_type: str
    scope_ref: str | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    @property
    def is_live(self) -> bool:
        return self.revoked_at is None


def authorization_mode() -> str:
    """The configured mode, validated where it is used (``docs/configuration.md`` §1)."""
    mode = str(getattr(settings, "ACADEMY_AUTHORIZATION_MODE", "role_plus_grants"))
    if mode not in AUTHORIZATION_MODES:
        raise ImproperlyConfigured(
            f"ACADEMY_AUTHORIZATION_MODE must be one of {AUTHORIZATION_MODES}, got {mode!r}"
        )
    return mode


def _grant_scope(grant: Grant) -> Scope:
    if grant.scope_type == "organization":
        return Scope.everything()
    return Scope.for_departments([grant.scope_ref] if grant.scope_ref else [])


def _live_grants(grants: Iterable[Grant], now: datetime) -> list[Grant]:
    live: list[Grant] = []
    for grant in grants:
        if not grant.is_live:
            continue
        if grant.expires_at is not None and grant.expires_at <= now:
            continue
        try:
            Capability(grant.capability)
        except ValueError as error:
            raise ValueError(f"unknown capability in grant: {grant.capability!r}") from error
        live.append(grant)
    return live


def role_capabilities(principal: Principal) -> Mapping[Capability, Scope]:
    """Hub role defaults of the compatibility mode (``docs/api.md`` §2).

    ``grants_only`` never reads this map; it exists so the old behaviour stays testable.
    """
    granted: dict[Capability, Scope] = {Capability.LEARN: Scope.everything()}
    own = Scope.for_departments(principal.department_refs)
    if "department_manager" in principal.roles:
        for capability in (Capability.MANAGE_CONTENT, Capability.ASSIGN, Capability.VIEW_REPORTS):
            granted[capability] = granted.get(capability, Scope()) | own
    if "platform_admin" in principal.roles:
        for capability in Capability:
            granted[capability] = Scope.everything()
    return MappingProxyType(granted)


@dataclass(frozen=True, slots=True)
class Access:
    """The resolved answer for one principal; never mutated after resolution."""

    principal: Principal
    capabilities: Mapping[Capability, Scope] = field(default_factory=dict)
    denied_reason: str | None = None

    def allows(self, capability: Capability | str, *, department_ref: str | None = None) -> bool:
        if self.denied_reason is not None:
            return False
        scope = self.capabilities.get(Capability(capability))
        return scope is not None and scope.covers(department_ref)

    def granted(self, capability: Capability | str) -> bool:
        """Capability present with any scope at all; department scope is checked per object."""
        return self.denied_reason is None and Capability(capability) in self.capabilities

    def covers_all_departments(self, capability: Capability | str) -> bool:
        scope = self.capabilities.get(Capability(capability))
        return self.denied_reason is None and scope is not None and scope.all_departments

    def require(self, capability: Capability | str, *, department_ref: str | None = None) -> None:
        """Raise the documented domain error instead of returning a false."""
        if self.denied_reason == "suspended":
            raise AccessSuspended("the account is suspended in Academy")
        if self.denied_reason == "inactive":
            raise InactiveAccount("the account is inactive")
        if not self.allows(capability, department_ref=department_ref):
            raise Forbidden(f"missing capability {Capability(capability)}")

    def require_organization_wide(self, capability: Capability | str) -> None:
        """Organization-wide writes need all-department scope, not one department's."""
        self.require(capability, department_ref=None)
        if not self.covers_all_departments(capability):
            raise Forbidden(f"{Capability(capability)} needs all-department scope")


def resolve_access(
    principal: Principal,
    grants: Sequence[Grant] = (),
    *,
    mode: str | None = None,
    now: datetime | None = None,
) -> Access:
    """Resolve effective capabilities for one principal (``CHARTER.md`` §3.1)."""
    if not principal.is_active:
        return Access(principal=principal, denied_reason="inactive")
    if principal.suspended:
        return Access(principal=principal, denied_reason="suspended")

    resolved_mode = mode or authorization_mode()
    if resolved_mode not in AUTHORIZATION_MODES:
        raise ImproperlyConfigured(f"unknown authorization mode: {resolved_mode!r}")

    granted: dict[Capability, Scope] = {}
    if resolved_mode == "role_plus_grants":
        granted.update(role_capabilities(principal))
    else:
        # H1: active members keep learning access; management needs a grant.
        granted[Capability.LEARN] = Scope.everything()

    for grant in _live_grants(grants, now or timezone.now()):
        capability = Capability(grant.capability)
        granted[capability] = granted.get(capability, Scope()) | _grant_scope(grant)

    return Access(principal=principal, capabilities=MappingProxyType(granted))
