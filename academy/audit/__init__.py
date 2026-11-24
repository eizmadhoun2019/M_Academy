"""The audit service — append-only accountability (ADR-009)."""

from academy.audit.service import AuditError, record

__all__ = ["AuditError", "record"]
