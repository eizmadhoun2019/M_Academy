"""Academy schema (``docs/domain-model.md``). Constraint types live in this package only."""

from __future__ import annotations

from academy.models.access import AccessSuspension
from academy.models.base import TenantManager, TenantModel, TenantQuerySet
from academy.models.catalog import Course, CourseVersion, Lesson, Section
from academy.models.grants import PermissionGrant
from academy.models.media import MediaAsset
from academy.models.operations import (
    AuditEvent,
    HubWebhookEvent,
    NotificationLog,
    ReminderLog,
)
from academy.models.progress import Assignment, CompletionRecord, Enrollment, LessonProgress
from academy.models.quiz import Quiz, QuizAttempt, QuizAttemptAnswer, QuizChoice, QuizQuestion
from academy.models.tenancy import BaseModel, Department, Membership, Organization, User

__all__ = [
    "AccessSuspension",
    "BaseModel",
    "Department",
    "Membership",
    "Organization",
    "User",
    "Assignment",
    "AuditEvent",
    "CompletionRecord",
    "Course",
    "CourseVersion",
    "Enrollment",
    "HubWebhookEvent",
    "Lesson",
    "LessonProgress",
    "MediaAsset",
    "NotificationLog",
    "PermissionGrant",
    "Quiz",
    "QuizAttempt",
    "QuizAttemptAnswer",
    "QuizChoice",
    "QuizQuestion",
    "ReminderLog",
    "Section",
    "TenantManager",
    "TenantModel",
    "TenantQuerySet",
]
