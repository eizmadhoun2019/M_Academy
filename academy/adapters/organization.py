"""Organization seam — Hub directory lookups (ADR-012, ADR-002).

Names and e-mail addresses are fetched at the moment they are needed and never stored, so a
lookup returns plain values that the caller uses and discards. Every method is tenant-scoped:
the organization is always an argument, and an unknown organization, department, role or
user yields an empty result rather than an error (``docs/hub-contract.md`` §3).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

#: ``docs/hub-contract.md`` §3 caps one ``users`` request at 50 distinct references.
MAX_USER_REFS = 50

#: The three Hub roles of ``docs/api.md`` §2.
ROLES = ("employee", "department_manager", "platform_admin")

#: Supported languages (``docs/configuration.md`` §1).
LANGUAGES = ("ar", "en")


@dataclass(frozen=True, slots=True)
class Department:
    """One directory department; ``parent_ref`` is ``None`` for a root department."""

    ref: str
    name: str
    parent_ref: str | None = None


@dataclass(frozen=True, slots=True)
class DirectoryUser:
    """A member as the Hub reports them. No name or address is stored by Academy."""

    user_ref: str
    display_name: str
    email: str | None
    language: str
    role: str
    department_refs: tuple[str, ...]
    manager_ref: str | None
    is_active: bool


@dataclass(frozen=True, slots=True)
class Role:
    """A role reference and its display name."""

    ref: str
    name: str


@runtime_checkable
class OrganizationAdapter(Protocol):
    """Read-only directory operations of ``docs/hub-contract.md`` §3."""

    def departments(self, organization_id: UUID) -> Sequence[Department]:
        """Every department of the organization (empty for an unknown tenant)."""
        ...

    def department_members(self, organization_id: UUID, department_ref: str) -> Sequence[str]:
        """Active members of the department and its descendants, by ``user_ref``."""
        ...

    def manager_of(self, organization_id: UUID, user_ref: str) -> str | None:
        """The manager's ``user_ref``, or ``None`` when there is none or the user is unknown."""
        ...

    def users(self, organization_id: UUID, user_refs: Sequence[str]) -> Sequence[DirectoryUser]:
        """Directory records for the requested references, unknown ones omitted.

        Implementations reject more than :data:`MAX_USER_REFS` distinct references with
        ``ValueError`` so a caller batches instead of opening an unbounded request.
        """
        ...

    def roles(self, organization_id: UUID) -> Sequence[Role]:
        """The role references of the organization."""
        ...

    def role_members(self, organization_id: UUID, role_ref: str) -> Sequence[str]:
        """Active members holding exactly ``role_ref``, by ``user_ref``."""
        ...
