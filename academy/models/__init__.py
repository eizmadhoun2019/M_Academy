"""Academy schema (``docs/domain-model.md``). Constraint types live in this package only."""

from __future__ import annotations

from academy.models.base import TenantManager, TenantModel, TenantQuerySet
from academy.models.catalog import Course, CourseVersion, Lesson, Section
from academy.models.media import MediaAsset
from academy.models.progress import Assignment, CompletionRecord, Enrollment, LessonProgress

__all__ = [
    "Assignment",
    "CompletionRecord",
    "Course",
    "CourseVersion",
    "Enrollment",
    "Lesson",
    "LessonProgress",
    "MediaAsset",
    "Section",
    "TenantManager",
    "TenantModel",
    "TenantQuerySet",
]
