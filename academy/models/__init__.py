"""Academy schema (``docs/domain-model.md``). Constraint types live in this package only."""

from __future__ import annotations

from academy.models.access import AccessSuspension
from academy.models.base import TenantManager, TenantModel, TenantQuerySet
from academy.models.catalog import Course, CourseVersion, Lesson, Section
from academy.models.media import MediaAsset
from academy.models.operations import AuditEvent, NotificationLog, ReminderLog
from academy.models.progress import Assignment, CompletionRecord, Enrollment, LessonProgress
from academy.models.quiz import Quiz, QuizAttempt, QuizAttemptAnswer, QuizChoice, QuizQuestion

__all__ = [
    "AccessSuspension",
    "Assignment",
    "AuditEvent",
    "CompletionRecord",
    "Course",
    "CourseVersion",
    "Enrollment",
    "Lesson",
    "LessonProgress",
    "MediaAsset",
    "NotificationLog",
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
