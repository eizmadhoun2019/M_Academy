"""Hub directory over HTTP — the ``OrganizationAdapter`` of ``docs/hub-contract.md`` §3.

Each lookup is tenant-scoped, capped at 50 references, cached for the configured TTL under the
per-tenant generation (so a membership webhook invalidates it), and raises
:class:`host_hub.http.HubUnavailable` when the Hub cannot answer — a directory outage is never
read as "no members".
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from django.core.cache import cache

from academy.adapters.organization import (
    MAX_USER_REFS,
    Department,
    DirectoryUser,
    Role,
)
from academy.hub.cache import directory_generation, directory_ttl
from host_hub.http import HubHttpClient, HubRejected


def _cache_key(organization_id: UUID, generation: int, name: str, *parts: str) -> str:
    joined = ":".join(parts)
    return f"macademy:hub:directory:{organization_id}:{generation}:{name}:{joined}"


class HubDirectory:
    """Read-only directory calls against the Hub service API."""

    def __init__(self, client: HubHttpClient | None = None) -> None:
        self.client = client or HubHttpClient()

    def _cached(
        self,
        organization_id: UUID,
        name: str,
        params: dict[str, str],
        *parts: str,
    ) -> dict[str, Any]:
        key = _cache_key(organization_id, directory_generation(organization_id), name, *parts)
        cached = cache.get(key)
        if isinstance(cached, dict):
            return cached
        try:
            data = self.client.get(name, {**params, "organization_id": str(organization_id)})
        except HubRejected as error:
            if error.status not in (403, 404):
                raise
            data = {"items": [], "next_cursor": None}
        cache.set(key, data, timeout=directory_ttl())
        return data

    def departments(self, organization_id: UUID) -> Sequence[Department]:
        data = self._cached(organization_id, "departments", {})
        return [
            Department(
                ref=str(item["ref"]),
                name=str(item["name"]),
                parent_ref=str(item["parent_ref"]) if item.get("parent_ref") else None,
            )
            for item in data.get("items", [])
        ]

    def department_members(self, organization_id: UUID, department_ref: str) -> Sequence[str]:
        data = self._cached(
            organization_id,
            "department_members",
            {"department_ref": department_ref},
            department_ref,
        )
        return [str(item["user_ref"]) for item in data.get("items", [])]

    def manager_of(self, organization_id: UUID, user_ref: str) -> str | None:
        data = self._cached(organization_id, "manager", {"user_ref": user_ref}, user_ref)
        items = data.get("items", [])
        if not items:
            return None
        manager = items[0].get("manager_ref")
        return str(manager) if manager else None

    def users(self, organization_id: UUID, user_refs: Sequence[str]) -> Sequence[DirectoryUser]:
        distinct = list(dict.fromkeys(user_refs))
        if len(distinct) > MAX_USER_REFS:
            raise ValueError(f"at most {MAX_USER_REFS} user references per request")
        if not distinct:
            return []
        pairs: list[tuple[str, str]] = [("organization_id", str(organization_id))]
        pairs.extend(("ref", ref) for ref in distinct)
        key = _cache_key(
            organization_id, directory_generation(organization_id), "users", ",".join(distinct)
        )
        data = cache.get(key)
        if not isinstance(data, dict):
            try:
                data = self.client.get("users", pairs)
            except HubRejected as error:
                if error.status not in (403, 404):
                    raise
                data = {"items": [], "next_cursor": None}
            cache.set(key, data, timeout=directory_ttl())
        return [
            DirectoryUser(
                user_ref=str(item["user_ref"]),
                display_name=str(item.get("display_name", "")),
                email=str(item["email"]) if item.get("email") else None,
                language=str(item.get("language", "ar")),
                role=str(item.get("role", "employee")),
                department_refs=tuple(str(ref) for ref in item.get("department_refs", [])),
                manager_ref=str(item["manager_ref"]) if item.get("manager_ref") else None,
                is_active=bool(item.get("is_active", False)),
            )
            for item in data.get("items", [])
        ]

    def roles(self, organization_id: UUID) -> Sequence[Role]:
        data = self._cached(organization_id, "roles", {})
        return [
            Role(ref=str(item["ref"]), name=str(item["name"])) for item in data.get("items", [])
        ]

    def role_members(self, organization_id: UUID, role_ref: str) -> Sequence[str]:
        data = self._cached(organization_id, "role_members", {"role": role_ref}, role_ref)
        return [str(item["user_ref"]) for item in data.get("items", [])]
