"""Target → recipient references — the one expansion selector of D-017.

The preview endpoint and the assignment write must agree, so both call
:func:`expand_target` and neither re-implements a target type. The directory has no
"everybody" route (``docs/hub-contract.md`` §3), so the ``organization`` target is the union of
the active members of every role the directory reports; a member always holds exactly one of
the three roles, which makes that union complete.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from academy.adapters.loader import load_adapter
from academy.exceptions import DomainValidationError
from academy.models import Assignment

#: D-017: a preview never counts past this, and a write never expands past it either.
MAX_RECIPIENTS = 5000


@dataclass(frozen=True, slots=True)
class Expansion:
    """The recipients of one target, already capped and ordered."""

    user_refs: tuple[str, ...]
    capped: bool

    @property
    def count(self) -> int:
        return len(self.user_refs)


def directory() -> Any:
    """The configured organisation seam (tests replace this attribute)."""
    return load_adapter("organization")()


def _members_of_role(organization_id: UUID, role_ref: str) -> Sequence[str]:
    return tuple(directory().role_members(organization_id, role_ref))


def _all_members(organization_id: UUID) -> tuple[str, ...]:
    refs: set[str] = set()
    for role in directory().roles(organization_id):
        refs.update(_members_of_role(organization_id, role.ref))
    return tuple(sorted(refs))


def resolve_target(
    organization_id: UUID, target_type: str, target_ref: str | None
) -> tuple[str, ...]:
    """Every ``user_ref`` the target reaches, before the cap, ordered and de-duplicated."""
    kind = str(target_type)
    if kind == Assignment.TargetType.USER:
        return (str(target_ref),)
    if kind == Assignment.TargetType.DEPARTMENT:
        return tuple(
            sorted(dict.fromkeys(directory().department_members(organization_id, str(target_ref))))
        )
    if kind == Assignment.TargetType.ROLE:
        return tuple(sorted(dict.fromkeys(_members_of_role(organization_id, str(target_ref)))))
    if kind == Assignment.TargetType.ORGANIZATION:
        return _all_members(organization_id)
    raise DomainValidationError(
        f"unknown target_type {kind!r}",
        fields={"target_type": "must be user, department, role or organization"},
    )


def expand_target(organization_id: UUID, target_type: str, target_ref: str | None) -> Expansion:
    """The recipients of one target, truncated to the documented cap."""
    refs = resolve_target(organization_id, target_type, target_ref)
    if len(refs) > MAX_RECIPIENTS:
        return Expansion(user_refs=refs[:MAX_RECIPIENTS], capped=True)
    return Expansion(user_refs=refs, capped=False)


__all__ = ["MAX_RECIPIENTS", "Expansion", "directory", "expand_target", "resolve_target"]
