"""Company context from the caller's single membership — T-026 CP3, D-043.

The session, a request body or a header never name the company: the account is looked up by its
legacy reference, its one membership supplies the organization, and a session-held
``membership_id`` is only cross-checked against that row. A stale or forged value therefore
resolves nothing instead of switching tenants.

``UNIQUE (user_id)`` on ``Membership`` (D-043) makes this a single indexed row per account.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from academy.models import Membership, Organization, User

#: The company roles an invitation may grant (D-028). Platform roles are global and are never
#: invited into a company; the dynamic catalogue replaces this tuple in T-028.
COMPANY_ROLES = ("employee", "department_manager")


@dataclass(frozen=True, slots=True)
class CompanyContext:
    """The account, its one active membership and that membership's company."""

    user: User
    membership: Membership
    organization: Organization

    @property
    def user_id(self) -> UUID:
        return self.user.pk

    @property
    def membership_id(self) -> UUID:
        return self.membership.pk

    @property
    def organization_id(self) -> UUID:
        return self.membership.organization_id

    @property
    def department_ref(self) -> str | None:
        """The legacy department reference of the membership, when it has one."""
        department = self.membership.department
        if department is None:
            return None
        return department.legacy_ref or None


def roles_for_user(user: User) -> list[str]:
    """The role codes a new session carries for this account.

    The membership is the source, so roles are derived from server state rather than trusted from
    the client's session payload. An account without a membership — a platform-only account —
    falls back to ``employee`` until the T-028 role catalogue supplies platform roles.
    """
    membership = Membership.objects.filter(user=user).first()
    if membership is None:
        return ["employee"]
    roles = [str(role) for role in (membership.roles or []) if str(role) in COMPANY_ROLES]
    return roles or ["employee"]


def account_for_ref(user_ref: str) -> User | None:
    """The global account imported from ``user_ref``, or ``None`` when it was never imported."""
    if not user_ref:
        return None
    return User.objects.filter(legacy_ref=user_ref).first()


def context_for_user(user: User) -> CompanyContext | None:
    """The active membership of ``user``, or ``None`` when it has none."""
    membership = Membership.objects.select_related("department").filter(user=user).first()
    if membership is None or membership.status != Membership.Status.ACTIVE:
        return None
    organization = Organization.objects.filter(pk=membership.organization_id).first()
    if organization is None:
        return None
    return CompanyContext(user=user, membership=membership, organization=organization)


def context_for_ref(user_ref: str) -> CompanyContext | None:
    """Resolve an active company context from a legacy account reference."""
    account = account_for_ref(user_ref)
    return context_for_user(account) if account is not None else None


def context_for_session(user_ref: str, membership_id: object = None) -> CompanyContext | None:
    """Resolve a session's company.

    The company always comes from the account's single membership. When the session also stores a
    ``membership_id``, it must name that same row: a tampered or stale id resolves nothing rather
    than selecting another company.
    """
    context = context_for_ref(user_ref)
    if context is None:
        return None
    if membership_id not in (None, "") and str(context.membership_id) != str(membership_id):
        return None
    return context


def account_without_membership(user_ref: str) -> bool:
    """True when the account exists but holds no active membership (403 ``membership_inactive``)."""
    account = account_for_ref(user_ref)
    return account is not None and context_for_user(account) is None
