"""Academy schema (``docs/domain-model.md``). Constraint types live in this package only."""

from __future__ import annotations

from academy.models.base import TenantManager, TenantModel, TenantQuerySet

__all__ = ["TenantManager", "TenantModel", "TenantQuerySet"]
