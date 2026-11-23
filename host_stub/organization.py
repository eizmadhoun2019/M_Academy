"""Development and test directory (in-memory, no Hub).

The caller seeds the directory (tests, the development shell); the seam's queries then behave
the way ``docs/hub-contract.md`` §3 describes: members of a department include its descendants,
only active memberships are returned, and another organization sees nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from academy.adapters.organization import (
    MAX_USER_REFS,
    Department,
    DirectoryUser,
    Role,
)


def _require_ref(what: str, ref: str) -> None:
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError(f"{what} reference must be a non-empty string")


@dataclass
class _Organization:
    departments: dict[str, Department] = field(default_factory=dict)
    users: dict[str, DirectoryUser] = field(default_factory=dict)
    roles: dict[str, Role] = field(default_factory=dict)


class StubDirectory:
    """In-memory organization directory seeded through the ``add_*`` methods."""

    def __init__(self) -> None:
        self._organizations: dict[UUID, _Organization] = {}

    # --- seeding ------------------------------------------------------------

    def _org(self, organization_id: UUID) -> _Organization:
        return self._organizations.setdefault(organization_id, _Organization())

    def add_department(
        self,
        organization_id: UUID,
        ref: str,
        name: str,
        *,
        parent_ref: str | None = None,
    ) -> None:
        _require_ref("department", ref)
        organization = self._org(organization_id)
        if ref in organization.departments:
            raise ValueError(f"department {ref!r} already exists")
        if parent_ref is not None and parent_ref not in organization.departments:
            raise ValueError(f"unknown parent department {parent_ref!r}")
        organization.departments[ref] = Department(ref=ref, name=name, parent_ref=parent_ref)

    def add_user(self, organization_id: UUID, user: DirectoryUser) -> None:
        _require_ref("user", user.user_ref)
        organization = self._org(organization_id)
        if user.user_ref in organization.users:
            raise ValueError(f"user {user.user_ref!r} already exists")
        unknown = [ref for ref in user.department_refs if ref not in organization.departments]
        if unknown:
            raise ValueError(f"unknown departments for {user.user_ref!r}: {unknown}")
        organization.users[user.user_ref] = user

    def add_role(self, organization_id: UUID, ref: str, name: str) -> None:
        _require_ref("role", ref)
        organization = self._org(organization_id)
        if ref in organization.roles:
            raise ValueError(f"role {ref!r} already exists")
        organization.roles[ref] = Role(ref=ref, name=name)

    # --- the seam -----------------------------------------------------------

    def departments(self, organization_id: UUID) -> Sequence[Department]:
        organization = self._organizations.get(organization_id)
        if organization is None:
            return ()
        return tuple(organization.departments[ref] for ref in sorted(organization.departments))

    def department_members(self, organization_id: UUID, department_ref: str) -> Sequence[str]:
        organization = self._organizations.get(organization_id)
        if organization is None or department_ref not in organization.departments:
            return ()
        scope = _with_descendants(organization.departments, department_ref)
        return tuple(
            sorted(
                user.user_ref
                for user in organization.users.values()
                if user.is_active and scope.intersection(user.department_refs)
            )
        )

    def manager_of(self, organization_id: UUID, user_ref: str) -> str | None:
        organization = self._organizations.get(organization_id)
        if organization is None:
            return None
        user = organization.users.get(user_ref)
        return None if user is None else user.manager_ref

    def users(self, organization_id: UUID, user_refs: Sequence[str]) -> Sequence[DirectoryUser]:
        requested = list(dict.fromkeys(user_refs))
        if len(requested) > MAX_USER_REFS:
            raise ValueError(
                f"at most {MAX_USER_REFS} user references per request, got {len(requested)}"
            )
        organization = self._organizations.get(organization_id)
        if organization is None:
            return ()
        return tuple(organization.users[ref] for ref in requested if ref in organization.users)

    def roles(self, organization_id: UUID) -> Sequence[Role]:
        organization = self._organizations.get(organization_id)
        if organization is None:
            return ()
        return tuple(organization.roles[ref] for ref in sorted(organization.roles))

    def role_members(self, organization_id: UUID, role_ref: str) -> Sequence[str]:
        organization = self._organizations.get(organization_id)
        if organization is None:
            return ()
        return tuple(
            sorted(
                user.user_ref
                for user in organization.users.values()
                if user.is_active and user.role == role_ref
            )
        )


def _with_descendants(departments: dict[str, Department], ref: str) -> set[str]:
    scope = {ref}
    grow = True
    while grow:
        grow = False
        for department in departments.values():
            if department.parent_ref in scope and department.ref not in scope:
                scope.add(department.ref)
                grow = True
    return scope
