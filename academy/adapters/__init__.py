"""Host seams (ARCHITECTURE.md §4). Only the loader resolves a host implementation.

These Protocols and their value types use the standard library only: a provider SDK belongs to
the implementation behind the seam, never to ``academy`` (gate G7).
"""

from __future__ import annotations

from academy.adapters.identity import IdentityAdapter
from academy.adapters.loader import ADAPTER_NAMES, load_adapter, reset_adapter_cache
from academy.adapters.notify import (
    CHANNELS,
    ActivityEvent,
    MailMessage,
    MailReceipt,
    NotifyAdapter,
)
from academy.adapters.organization import (
    LANGUAGES,
    MAX_USER_REFS,
    ROLES,
    Department,
    DirectoryUser,
    OrganizationAdapter,
    Role,
)
from academy.adapters.storage import (
    ObjectStat,
    StorageAdapter,
    organization_prefix,
    validate_key,
    validate_prefix,
)

__all__ = [
    "ADAPTER_NAMES",
    "CHANNELS",
    "LANGUAGES",
    "MAX_USER_REFS",
    "ROLES",
    "ActivityEvent",
    "Department",
    "DirectoryUser",
    "IdentityAdapter",
    "MailMessage",
    "MailReceipt",
    "NotifyAdapter",
    "ObjectStat",
    "OrganizationAdapter",
    "Role",
    "StorageAdapter",
    "load_adapter",
    "organization_prefix",
    "reset_adapter_cache",
    "validate_key",
    "validate_prefix",
]
