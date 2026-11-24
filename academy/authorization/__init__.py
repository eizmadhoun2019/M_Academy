"""Authorization: capabilities, scopes and the H1 `grants_only` policy."""

from __future__ import annotations

from academy.authorization.core import (
    AUTHORIZATION_MODES,
    MANAGEMENT_CAPABILITIES,
    Access,
    Capability,
    Grant,
    Principal,
    Scope,
    authorization_mode,
    resolve_access,
    role_capabilities,
)

__all__ = [
    "AUTHORIZATION_MODES",
    "MANAGEMENT_CAPABILITIES",
    "Access",
    "Capability",
    "Grant",
    "Principal",
    "Scope",
    "authorization_mode",
    "resolve_access",
    "role_capabilities",
]
