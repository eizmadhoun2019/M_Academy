"""T-008 acceptance: quiz, reminder, notification and audit tables.

Phase 1 ships the quiz schema without behaviour, so these tests pin the shape the Phase 2 code
will rely on. The operational tables are tested through the rows their future services must
not be able to write twice.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from django.apps import apps
from django.db import IntegrityError, transaction
from django.utils import timezone

from academy.models import (
    AuditEvent,
    Course,
    CourseVersion,
    Enrollment,
    Lesson,
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

pytestmark = pytest.mark.django_db

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
OTHER_ORG = UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11")


@pytest.fixture
def course() -> Course:
    return Course.objects.create(organization_id=ORG, title="Sample course", created_by_ref="u-10")


@pytest.fixture
def version(course: Course) -> CourseVersion:
    return CourseVersion.objects.create(
        organization_id=ORG, course=course, version_number=1, created_by_ref="u-10"
    )


@pytest.fixture
def lesson(version: CourseVersion) -> Lesson:
    section = Section.objects.create(
        organization_id=ORG, version=version, title="Intro", position=1
    )
    return Lesson.objects.create(
        organization_id=ORG,
        section=section,
        title="Lesson one",
        position=1,
        content_type=Lesson.ContentType.TEXT,
        body="Read this.",
    )


@pytest.fixture
def enrollment(course: Course, version: CourseVersion) -> Enrollment:
    return Enrollment.objects.create(
        organization_id=ORG, course=course, course_version=version, user_ref="u-20"
    )


@pytest.fixture
def quiz(version: CourseVersion, lesson: Lesson) -> Quiz:
    return Quiz.objects.create(
        organization_id=ORG, version=version, lesson=lesson, title="Check your knowledge"
    )


def make_question(quiz: Quiz, **overrides: object) -> QuizQuestion:
    values: dict[str, object] = {
        "organization_id": ORG,
        "quiz": quiz,
        "position": 1,
        "prompt": "What is the policy?",
    }
    values.update(overrides)
    return QuizQuestion.objects.create(**values)


def make_choice(question: QuizQuestion, **overrides: object) -> QuizChoice:
    values: dict[str, object] = {
        "organization_id": ORG,
        "question": question,
        "position": 1,
        "label": "The right answer",
        "is_correct": True,
    }
    values.update(overrides)
    return QuizChoice.objects.create(**values)


def make_attempt(quiz: Quiz, enrollment: Enrollment, **overrides: object) -> QuizAttempt:
    values: dict[str, object] = {
        "organization_id": ORG,
        "quiz": quiz,
        "enrollment": enrollment,
        "attempt_number": 1,
        "started_at": timezone.now(),
    }
    values.update(overrides)
    return QuizAttempt.objects.create(**values)


def test_every_academy_model_is_a_tenant_model() -> None:
    models = list(apps.get_app_config("academy").get_models())
    global_models = {
        "AccountToken",
        "MFADevice",
        "Organization",
        "RecoveryCode",
        "User",
        "UserSession",
    }

    assert models
    assert {model.__name__ for model in models if not issubclass(model, TenantModel)} == (
        global_models
    )


def test_quiz_defaults(quiz: Quiz) -> None:
    assert quiz.pass_percent == 70
    assert quiz.max_attempts == 3
    assert quiz.lesson is not None


def test_quiz_pass_percent_stays_in_range(version: CourseVersion) -> None:
    for value in (-1, 101):
        with pytest.raises(IntegrityError), transaction.atomic():
            Quiz.objects.create(
                organization_id=ORG, version=version, title="Bad", pass_percent=value
            )


def test_a_quiz_needs_at_least_one_attempt(version: CourseVersion) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Quiz.objects.create(
            organization_id=ORG, version=version, title="No attempts", max_attempts=0
        )


def test_a_quiz_title_cannot_be_blank(version: CourseVersion) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Quiz.objects.create(organization_id=ORG, version=version, title="  ")


def test_question_positions_are_unique_per_quiz(quiz: Quiz) -> None:
    make_question(quiz)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_question(quiz, prompt="Second question")


def test_question_kind_must_be_known(quiz: Quiz) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_question(quiz, kind="true_false")


def test_a_question_prompt_cannot_be_blank(quiz: Quiz) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_question(quiz, prompt="   ")


def test_choice_positions_are_unique_per_question(quiz: Quiz) -> None:
    question = make_question(quiz)
    make_choice(question)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_choice(question, label="Another answer", is_correct=False)


def test_a_choice_label_cannot_be_blank(quiz: Quiz) -> None:
    question = make_question(quiz)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_choice(question, label=" ")


def test_attempt_numbers_are_unique_per_quiz_and_enrollment(
    quiz: Quiz, enrollment: Enrollment
) -> None:
    make_attempt(quiz, enrollment)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_attempt(quiz, enrollment)


def test_attempt_number_starts_at_one(quiz: Quiz, enrollment: Enrollment) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_attempt(quiz, enrollment, attempt_number=0)


def test_attempt_score_stays_in_range(quiz: Quiz, enrollment: Enrollment) -> None:
    for number, value in enumerate((Decimal("-0.01"), Decimal("100.01")), start=1):
        with pytest.raises(IntegrityError), transaction.atomic():
            make_attempt(quiz, enrollment, attempt_number=number, score_percent=value)


def test_a_submitted_attempt_saves(quiz: Quiz, enrollment: Enrollment) -> None:
    attempt = make_attempt(
        quiz,
        enrollment,
        submitted_at=timezone.now(),
        score_percent=Decimal("80.00"),
        passed=True,
    )

    assert attempt.passed is True
    assert attempt.score_percent == Decimal("80.00")


def test_answers_are_unique_per_attempt_and_question(quiz: Quiz, enrollment: Enrollment) -> None:
    question = make_question(quiz)
    attempt = make_attempt(quiz, enrollment)
    QuizAttemptAnswer.objects.create(
        organization_id=ORG, attempt=attempt, question=question, choice_ids=[], correct=False
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        QuizAttemptAnswer.objects.create(
            organization_id=ORG, attempt=attempt, question=question, choice_ids=[]
        )


def test_a_reminder_is_sent_once_per_kind_and_recipient(enrollment: Enrollment) -> None:
    values = {
        "organization_id": ORG,
        "enrollment": enrollment,
        "kind": ReminderLog.Kind.DUE,
        "recipient_ref": "u-20",
    }
    ReminderLog.objects.create(**values)

    with pytest.raises(IntegrityError), transaction.atomic():
        ReminderLog.objects.create(**values)


def test_a_reminder_kind_must_be_known(enrollment: Enrollment) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        ReminderLog.objects.create(
            organization_id=ORG,
            enrollment=enrollment,
            kind="due_plus_30",
            recipient_ref="u-20",
        )


def test_a_notification_is_unique_per_dedupe_key_and_channel() -> None:
    values = {
        "organization_id": ORG,
        "kind": NotificationLog.Kind.COURSE_ASSIGNED,
        "dedupe_key": "assigned:a-12:u-42",
        "recipient_ref": "u-42",
    }
    NotificationLog.objects.create(**values)

    with pytest.raises(IntegrityError), transaction.atomic():
        NotificationLog.objects.create(**values)
    # Another channel is a separate message, so it is allowed.
    NotificationLog.objects.create(**values, channel=NotificationLog.Channel.IN_APP)


def test_a_sent_notification_must_carry_its_timestamp() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        NotificationLog.objects.create(
            organization_id=ORG,
            kind=NotificationLog.Kind.COURSE_COMPLETED,
            dedupe_key="completed:e-79",
            recipient_ref="u-42",
            status=NotificationLog.Status.SENT,
        )


def test_a_sent_notification_saves_with_its_timestamp() -> None:
    row = NotificationLog.objects.create(
        organization_id=ORG,
        kind=NotificationLog.Kind.COURSE_COMPLETED,
        dedupe_key="completed:e-79",
        recipient_ref="u-42",
        status=NotificationLog.Status.SENT,
        sent_at=timezone.now(),
    )

    assert row.attempt_count == 0
    assert row.channel == NotificationLog.Channel.EMAIL


def test_a_notification_status_must_be_known() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        NotificationLog.objects.create(
            organization_id=ORG,
            kind=NotificationLog.Kind.LEARNER_COMPLETED,
            dedupe_key="learner:e-1",
            recipient_ref="u-42",
            status="delivered",
        )


def test_audit_events_are_unique_per_organization_and_event_id() -> None:
    event_id = uuid4()
    values = {
        "organization_id": ORG,
        "event_id": event_id,
        "actor_ref": "u-10",
        "action": "course.published",
        "object_type": "CourseVersion",
        "object_id": str(uuid4()),
    }
    AuditEvent.objects.create(**values)

    with pytest.raises(IntegrityError), transaction.atomic():
        AuditEvent.objects.create(**values)
    # The same event id in another organization is a different event.
    AuditEvent.objects.create(**{**values, "organization_id": OTHER_ORG})


def test_an_audit_event_stores_ids_only() -> None:
    row = AuditEvent.objects.create(
        organization_id=ORG,
        actor_ref="system",
        action="grant.denied",
        object_type="PermissionGrant",
        object_id="g-1",
    )

    assert row.metadata == {}
    assert row.occurred_at is not None
