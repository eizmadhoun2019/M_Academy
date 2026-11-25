"""Test factories for every Academy table, plus the tenant-isolation detector.

The factories build the smallest valid graph for one row, always inside the organization they
are given, so a suite can create the same table in two organizations and then prove that
``for_org`` never returns the other one. They hold no product rules: a value that a check
forbids is still forbidden, which is what the schema tests rely on.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from typing import Any
from uuid import UUID

from academy.models import (
    AccessSuspension,
    Assignment,
    AuditEvent,
    CompletionRecord,
    Course,
    CourseVersion,
    Enrollment,
    HubWebhookEvent,
    Lesson,
    LessonProgress,
    MediaAsset,
    NotificationLog,
    Quiz,
    QuizAttempt,
    QuizAttemptAnswer,
    QuizChoice,
    QuizQuestion,
    ReminderLog,
    Section,
    TenantModel,
)


def make_webhook_event(organization_id: UUID, **overrides: Any) -> HubWebhookEvent:
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "event_id": uuid.uuid4(),
        "event_type": "member_changed",
        "user_ref": "u-42",
        "body_sha256": "0" * 64,
    }
    values.update(overrides)
    return HubWebhookEvent.objects.create(**values)


def make_suspension(organization_id: UUID, **overrides: Any) -> AccessSuspension:
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "user_ref": "u-suspended",
        "reason": "Policy review",
        "suspended_by_ref": "u-admin",
    }
    values.update(overrides)
    return AccessSuspension.objects.create(**values)


def make_course(organization_id: UUID, **overrides: Any) -> Course:
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "title": "Sample course",
        "created_by_ref": "u-author",
    }
    values.update(overrides)
    return Course.objects.create(**values)


def make_version(
    organization_id: UUID, course: Course | None = None, **overrides: Any
) -> CourseVersion:
    course = course or make_course(organization_id)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "course": course,
        "version_number": 1,
        "created_by_ref": "u-author",
    }
    values.update(overrides)
    return CourseVersion.objects.create(**values)


def make_section(
    organization_id: UUID, version: CourseVersion | None = None, **overrides: Any
) -> Section:
    version = version or make_version(organization_id)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "version": version,
        "title": "Introduction",
        "position": 1,
    }
    values.update(overrides)
    return Section.objects.create(**values)


def make_media(organization_id: UUID, **overrides: Any) -> MediaAsset:
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "kind": MediaAsset.Kind.VIDEO,
        "created_by_ref": "u-author",
    }
    values.update(overrides)
    return MediaAsset.objects.create(**values)


def make_lesson(organization_id: UUID, section: Section | None = None, **overrides: Any) -> Lesson:
    section = section or make_section(organization_id)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "section": section,
        "title": "A lesson",
        "position": 1,
        "content_type": Lesson.ContentType.TEXT,
        "body": "Read this.",
    }
    values.update(overrides)
    return Lesson.objects.create(**values)


def make_assignment(
    organization_id: UUID, course: Course | None = None, **overrides: Any
) -> Assignment:
    course = course or make_course(organization_id)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "course": course,
        "target_type": Assignment.TargetType.DEPARTMENT,
        "target_ref": "dep-1",
        "assigned_by_ref": "u-manager",
    }
    values.update(overrides)
    return Assignment.objects.create(**values)


def make_enrollment(
    organization_id: UUID,
    course: Course | None = None,
    version: CourseVersion | None = None,
    **overrides: Any,
) -> Enrollment:
    course = course or make_course(organization_id)
    version = version or make_version(organization_id, course=course)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "course": course,
        "course_version": version,
        "user_ref": "u-learner",
    }
    values.update(overrides)
    return Enrollment.objects.create(**values)


def make_progress(
    organization_id: UUID,
    enrollment: Enrollment | None = None,
    lesson: Lesson | None = None,
    **overrides: Any,
) -> LessonProgress:
    enrollment = enrollment or make_enrollment(organization_id)
    lesson = lesson or make_lesson(
        organization_id, section=make_section(organization_id, version=enrollment.course_version)
    )
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "enrollment": enrollment,
        "lesson": lesson,
    }
    values.update(overrides)
    return LessonProgress.objects.create(**values)


def make_completion(
    organization_id: UUID, enrollment: Enrollment | None = None, **overrides: Any
) -> CompletionRecord:
    enrollment = enrollment or make_enrollment(organization_id)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "enrollment": enrollment,
        "course_id": enrollment.course.pk,
        "course_version_id": enrollment.course_version.pk,
        "user_ref": enrollment.user_ref,
        "completed_at": enrollment.created_at,
        "actor_ref": enrollment.user_ref,
    }
    values.update(overrides)
    return CompletionRecord.objects.create(**values)


def make_quiz(
    organization_id: UUID,
    version: CourseVersion | None = None,
    lesson: Lesson | None = None,
    **overrides: Any,
) -> Quiz:
    version = version or make_version(organization_id)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "version": version,
        "lesson": lesson,
        "title": "Knowledge check",
    }
    values.update(overrides)
    return Quiz.objects.create(**values)


def make_question(
    organization_id: UUID, quiz: Quiz | None = None, **overrides: Any
) -> QuizQuestion:
    quiz = quiz or make_quiz(organization_id)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "quiz": quiz,
        "position": 1,
        "prompt": "What is the policy?",
    }
    values.update(overrides)
    return QuizQuestion.objects.create(**values)


def make_choice(
    organization_id: UUID, question: QuizQuestion | None = None, **overrides: Any
) -> QuizChoice:
    question = question or make_question(organization_id)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "question": question,
        "position": 1,
        "label": "The right answer",
        "is_correct": True,
    }
    values.update(overrides)
    return QuizChoice.objects.create(**values)


def make_attempt(
    organization_id: UUID,
    quiz: Quiz | None = None,
    enrollment: Enrollment | None = None,
    **overrides: Any,
) -> QuizAttempt:
    quiz = quiz or make_quiz(organization_id)
    enrollment = enrollment or make_enrollment(organization_id)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "quiz": quiz,
        "enrollment": enrollment,
        "attempt_number": 1,
        "started_at": enrollment.created_at,
    }
    values.update(overrides)
    return QuizAttempt.objects.create(**values)


def make_answer(
    organization_id: UUID,
    attempt: QuizAttempt | None = None,
    question: QuizQuestion | None = None,
    **overrides: Any,
) -> QuizAttemptAnswer:
    attempt = attempt or make_attempt(organization_id)
    question = question or make_question(organization_id)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "attempt": attempt,
        "question": question,
        "choice_ids": [],
        "correct": False,
    }
    values.update(overrides)
    return QuizAttemptAnswer.objects.create(**values)


def make_reminder(
    organization_id: UUID, enrollment: Enrollment | None = None, **overrides: Any
) -> ReminderLog:
    enrollment = enrollment or make_enrollment(organization_id)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "enrollment": enrollment,
        "kind": ReminderLog.Kind.DUE,
        "recipient_ref": "u-learner",
    }
    values.update(overrides)
    return ReminderLog.objects.create(**values)


def make_notification(organization_id: UUID, **overrides: Any) -> NotificationLog:
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "kind": NotificationLog.Kind.COURSE_ASSIGNED,
        "dedupe_key": f"assigned:{uuid.uuid4()}",
        "recipient_ref": "u-learner",
    }
    values.update(overrides)
    return NotificationLog.objects.create(**values)


def make_audit(organization_id: UUID, **overrides: Any) -> AuditEvent:
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "actor_ref": "u-manager",
        "action": "course.created",
        "object_type": "Course",
        "object_id": str(uuid.uuid4()),
    }
    values.update(overrides)
    return AuditEvent.objects.create(**values)


FACTORIES: dict[type[TenantModel], Callable[[UUID], TenantModel]] = {
    Course: make_course,
    CourseVersion: make_version,
    Section: make_section,
    Lesson: make_lesson,
    MediaAsset: make_media,
    Assignment: make_assignment,
    Enrollment: make_enrollment,
    LessonProgress: make_progress,
    CompletionRecord: make_completion,
    Quiz: make_quiz,
    QuizQuestion: make_question,
    QuizChoice: make_choice,
    QuizAttempt: make_attempt,
    QuizAttemptAnswer: make_answer,
    ReminderLog: make_reminder,
    NotificationLog: make_notification,
    AuditEvent: make_audit,
    AccessSuspension: make_suspension,
    HubWebhookEvent: make_webhook_event,
}


def make_row[ModelT: TenantModel](model: type[ModelT], organization_id: UUID) -> ModelT:
    """Build one valid row of ``model`` inside ``organization_id``."""
    row = FACTORIES[model](organization_id)
    assert isinstance(row, model)
    return row


def assert_only_own_rows(model: type[TenantModel], organization_id: UUID) -> None:
    """Raise when a row of another organization is visible through a query.

    The detector is exported so the isolation suite can prove that it actually fires: a
    deliberately unscoped query is fed through it and must fail.
    """
    rows: Iterable[TenantModel] = model.objects.all()
    foreign = [row for row in rows if row.organization_id != organization_id]
    if foreign:
        raise AssertionError(
            f"{model.__name__} leaked {len(foreign)} row(s) from another organization"
        )
