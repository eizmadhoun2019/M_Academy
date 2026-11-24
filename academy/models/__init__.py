"""Academy schema (``docs/domain-model.md``). Constraint types live in this package only."""

from __future__ import annotations

from academy.models.base import TenantManager, TenantModel, TenantQuerySet
from academy.models.catalog import Course, CourseVersion, Lesson, Section
from academy.models.media import MediaAsset

__all__ = [
    "Course",
    "CourseVersion",
    "Lesson",
    "MediaAsset",
    "Section",
    "TenantManager",
    "TenantModel",
    "TenantQuerySet",
]
