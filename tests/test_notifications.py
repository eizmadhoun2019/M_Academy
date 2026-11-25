"""T-021 acceptance: copy, queueing and delivery state (``docs/notifications.md`` §5).

The catalogue half renders every key in both languages without touching the database. The
delivery half drives the seam directly — a recording transport plus a seeded stub directory —
so each rule of §1 is one assertion: one row per ``(dedupe_key, channel)``, ``skipped`` with a
stable code for a message that must not leave, and ``pending`` with a counted attempt when the
directory itself is unreachable.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from django.conf import settings
from django.utils import timezone
from factories import (
    make_assignment,
    make_course,
    make_enrollment,
    make_notification,
    make_version,
)

from academy.adapters.organization import DirectoryUser
from academy.events import DomainEvent, clear_handlers, dispatch
from academy.models import NotificationLog
from academy.notifications import catalogue, handlers, service
from host_stub.notify import RecordingNotifier
from host_stub.organization import StubDirectory

pytestmark = pytest.mark.django_db

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")

#: Every variable the table of §3 uses; a key that needs fewer simply ignores the extras.
VARIABLES = {
    "course_title": "أساسيات المنصة",
    "due_date": "15 نوفمبر 2026",
    "progress": "40",
    "org": "مشيد",
    "learner_name": "سارة العلي",
    "completed_date": "20 نوفمبر 2026",
    "count": "2",
}


def member(
    ref: str, *, email: str | None, active: bool = True, manager: str | None = None
) -> DirectoryUser:
    return DirectoryUser(
        user_ref=ref,
        display_name=f"الاسم {ref}",
        email=email,
        language="ar",
        role="employee",
        department_refs=("dep-1",),
        manager_ref=manager,
        is_active=active,
    )


@pytest.fixture
def directory(monkeypatch: pytest.MonkeyPatch) -> StubDirectory:
    stub = StubDirectory()
    stub.add_department(ORG, "dep-1", "Training")
    stub.add_user(ORG, member("u-learner", email="learner@example.test", manager="u-manager"))
    stub.add_user(ORG, member("u-two", email="two@example.test", manager="u-manager"))
    stub.add_user(ORG, member("u-manager", email="manager@example.test"))
    stub.add_user(ORG, member("u-gone", email=None, active=False, manager="u-manager"))
    monkeypatch.setattr(service, "directory", lambda: stub)
    return stub


@pytest.fixture
def notifier(monkeypatch: pytest.MonkeyPatch) -> RecordingNotifier:
    stub = RecordingNotifier()
    monkeypatch.setattr(service, "adapter", lambda: stub)
    return stub


@pytest.fixture(autouse=True)
def _subscriptions() -> Iterator[None]:
    handlers.subscribe_all()
    yield
    handlers.unsubscribe_all()
    clear_handlers()


def graph(
    *,
    user_ref: str = "u-learner",
    actor: str = "u-manager",
    due_at: Any = None,
    status: str = "active",
    completed_at: Any = None,
    cancelled_at: Any = None,
) -> tuple[Any, Any]:
    """One course, its assignment and the enrollment that assignment expanded into."""
    course = make_course(ORG)
    version = make_version(ORG, course=course)
    assignment = make_assignment(ORG, course=course, assigned_by_ref=actor)
    enrollment = make_enrollment(
        ORG,
        course=course,
        version=version,
        assignment=assignment,
        user_ref=user_ref,
        due_at=due_at,
        status=status,
        completed_at=completed_at,
        cancelled_at=cancelled_at,
    )
    return assignment, enrollment


def queue_assigned(assignment: Any, user_ref: str = "u-learner") -> list[NotificationLog]:
    return service.queue(
        NotificationLog.Kind.COURSE_ASSIGNED,
        organization_id=ORG,
        dedupe_key=f"assigned:{assignment.pk}:{user_ref}",
        recipient_ref=user_ref,
    )


# --- catalogue --------------------------------------------------------------


@pytest.mark.parametrize("spec", catalogue.SPECS, ids=lambda row: row.key)
def test_every_key_renders_in_both_languages_without_a_leftover_placeholder(
    spec: catalogue.MessageSpec,
) -> None:
    for language in catalogue.LANGUAGES:
        rendered = catalogue.render(
            spec.kind,
            language=language,
            organization_name="مشيد",
            variables=VARIABLES,
        )
        assert "{" not in rendered.subject
        assert "{" not in rendered.text
        assert "{" not in rendered.html
        assert len(rendered.subject) <= catalogue.MAX_SUBJECT
        assert rendered.direction == catalogue.DIRECTIONS[language]
        assert f'dir="{catalogue.DIRECTIONS[language]}"' in rendered.html
        assert rendered.text.strip()
    arabic = catalogue.render(
        spec.kind, language="ar", organization_name="مشيد", variables=VARIABLES
    )
    english = catalogue.render(
        spec.kind, language="en", organization_name="مشيد", variables=VARIABLES
    )
    assert arabic.subject != english.subject


def test_a_missing_variable_is_refused_instead_of_shipped() -> None:
    with pytest.raises(KeyError):
        catalogue.render(
            "course_assigned",
            language="ar",
            organization_name="مشيد",
            variables={"course_title": "أساسيات المنصة"},
        )


def test_the_digest_replaces_only_the_rows_the_count_and_the_footer() -> None:
    rows = [
        catalogue.DigestRow(
            employee="موظف أ", course="أساسيات المنصة", due="15 نوفمبر 2026", days=3, progress="40%"
        ),
        catalogue.DigestRow(
            employee="موظف ب", course="هوية مشيد", due="14 نوفمبر 2026", days=4, progress="20%"
        ),
    ]
    rendered = catalogue.render_digest(
        language="ar",
        organization_name="مشيد",
        rows=rows,
        url="https://academy.example.test/academy/manage/team/",
        now=timezone.now(),
    )

    assert "2" in rendered.html
    for row in rows:
        assert row.employee in rendered.html
        assert row.employee in rendered.text
    assert "بيانات تجريبية" not in rendered.html
    assert "أكاديمية مشيد" in rendered.html
    assert f"{timezone.now().year}" in rendered.html
    assert rendered.direction == "rtl"


# --- queueing ---------------------------------------------------------------


def test_queue_is_idempotent_per_dedupe_key_and_channel() -> None:
    assignment, _ = graph()

    first = queue_assigned(assignment)
    second = queue_assigned(assignment)

    assert second == []
    assert {row.channel for row in first} == {"email", "in_app"}
    assert NotificationLog.objects.filter(organization_id=ORG).count() == 2


def test_an_unknown_kind_is_refused_before_the_insert() -> None:
    with pytest.raises(ValueError, match="unknown notification kind"):
        service.queue(
            "not_a_kind",
            organization_id=ORG,
            dedupe_key="x:y",
            recipient_ref="u-learner",
        )


# --- delivery ---------------------------------------------------------------


def test_delivery_marks_sent_and_reaches_the_transport(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    assignment, _ = graph()
    row = queue_assigned(assignment)[0]

    assert service.deliver(row) == NotificationLog.Status.SENT

    row.refresh_from_db()
    assert row.status == NotificationLog.Status.SENT
    assert row.sent_at is not None
    assert len(notifier.sent_mail) == 1
    _, message = notifier.sent_mail[0]
    assert message.recipient_ref == "u-learner"
    assert message.idempotency_key == row.dedupe_key
    assert message.payload is not None
    assert message.payload["link"].startswith(settings.ACADEMY_HUB_ORIGIN.rstrip("/"))
    assert "/academy/my/" in message.payload["link"]
    assert 'dir="rtl"' in str(message.payload["html"])


def test_a_second_delivery_short_circuits_on_sent(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    assignment, _ = graph()
    row = queue_assigned(assignment)[0]

    service.deliver(row)
    service.deliver(row)

    assert len(notifier.sent_mail) == 1


def test_in_app_rows_complete_without_the_transport(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    assignment, _ = graph()
    in_app = next(row for row in queue_assigned(assignment) if row.channel == "in_app")

    assert service.deliver(in_app) == NotificationLog.Status.SENT
    assert notifier.sent_mail == ()


def test_a_completed_enrollment_skips_the_assignment_message(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    assignment, _ = graph(status="completed", completed_at=timezone.now())
    row = queue_assigned(assignment)[0]

    assert service.deliver(row) == NotificationLog.Status.SKIPPED
    row.refresh_from_db()
    assert row.error_code == service.SKIPPED_COMPLETED
    assert notifier.sent_mail == ()


def test_a_cancelled_enrollment_skips_the_assignment_message(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    assignment, _ = graph(status="cancelled", cancelled_at=timezone.now())
    row = queue_assigned(assignment)[0]

    assert service.deliver(row) == NotificationLog.Status.SKIPPED
    row.refresh_from_db()
    assert row.error_code == service.SKIPPED_CANCELLED


def test_an_inactive_recipient_is_skipped_with_the_documented_code(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    assignment, _ = graph(user_ref="u-gone")
    row = queue_assigned(assignment, "u-gone")[0]

    assert service.deliver(row) == NotificationLog.Status.SKIPPED
    row.refresh_from_db()
    assert row.error_code == service.SKIPPED_INACTIVE
    assert notifier.sent_mail == ()


def test_a_directory_outage_leaves_the_row_pending_with_its_attempt_counted(
    monkeypatch: pytest.MonkeyPatch, notifier: RecordingNotifier
) -> None:
    assignment, _ = graph()
    row = queue_assigned(assignment)[0]

    def unavailable() -> Any:
        raise RuntimeError("directory down")

    monkeypatch.setattr(service, "directory", unavailable)
    with pytest.raises(RuntimeError):
        service.deliver(row)

    row.refresh_from_db()
    assert row.status == NotificationLog.Status.PENDING
    assert row.attempt_count == 1
    assert row.error_code == service.DIRECTORY_UNAVAILABLE
    assert notifier.sent_mail == ()


def test_the_completion_message_carries_the_course_title(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    _, enrollment = graph(status="completed", completed_at=timezone.now())
    row = make_notification(
        ORG,
        kind=NotificationLog.Kind.COURSE_COMPLETED,
        dedupe_key=f"completed:{enrollment.pk}",
        recipient_ref="u-learner",
    )

    assert service.deliver(row) == NotificationLog.Status.SENT
    _, message = notifier.sent_mail[0]
    assert enrollment.course.title in message.title


# --- events -----------------------------------------------------------------


def test_creating_an_enrollment_queues_one_assignment_message(
    directory: StubDirectory,
) -> None:
    assignment, enrollment = graph()
    payload = {
        "enrollment_id": str(enrollment.pk),
        "assignment_id": str(assignment.pk),
        "user_ref": "u-learner",
    }

    dispatch(DomainEvent(name=handlers.ENROLLMENT_CREATED, organization_id=ORG, payload=payload))
    dispatch(DomainEvent(name=handlers.ENROLLMENT_CREATED, organization_id=ORG, payload=payload))

    rows = NotificationLog.objects.filter(organization_id=ORG)
    assert rows.count() == 2
    assert {row.kind for row in rows} == {NotificationLog.Kind.COURSE_ASSIGNED}
    assert {row.dedupe_key for row in rows} == {f"assigned:{assignment.pk}:u-learner"}


def test_a_manual_enrollment_queues_nothing(directory: StubDirectory) -> None:
    _, enrollment = graph()
    dispatch(
        DomainEvent(
            name=handlers.ENROLLMENT_CREATED,
            organization_id=ORG,
            payload={"enrollment_id": str(enrollment.pk), "assignment_id": None},
        )
    )

    assert NotificationLog.objects.filter(organization_id=ORG).count() == 0


def test_completion_notifies_the_learner_and_the_assigner(
    directory: StubDirectory,
) -> None:
    _, enrollment = graph(status="completed", completed_at=timezone.now())

    dispatch(
        DomainEvent(
            name=handlers.ENROLLMENT_COMPLETED,
            organization_id=ORG,
            payload={"enrollment_id": str(enrollment.pk), "user_ref": "u-learner"},
        )
    )
    dispatch(
        DomainEvent(
            name=handlers.ENROLLMENT_COMPLETED,
            organization_id=ORG,
            payload={"enrollment_id": str(enrollment.pk), "user_ref": "u-learner"},
        )
    )

    rows = list(NotificationLog.objects.filter(organization_id=ORG))
    learner = [row for row in rows if row.kind == NotificationLog.Kind.COURSE_COMPLETED]
    manager = [row for row in rows if row.kind == NotificationLog.Kind.LEARNER_COMPLETED]
    assert len(learner) == 2  # email + in_app
    assert len(manager) == 1  # in-app only in this phase
    assert manager[0].recipient_ref == "u-manager"
    assert manager[0].channel == NotificationLog.Channel.IN_APP


def test_an_automatic_assignment_falls_back_to_the_hub_manager(
    directory: StubDirectory,
) -> None:
    _, enrollment = graph(actor="system", status="completed", completed_at=timezone.now())

    dispatch(
        DomainEvent(
            name=handlers.ENROLLMENT_COMPLETED,
            organization_id=ORG,
            payload={"enrollment_id": str(enrollment.pk), "user_ref": "u-learner"},
        )
    )

    manager = NotificationLog.objects.get(kind=NotificationLog.Kind.LEARNER_COMPLETED)
    assert manager.recipient_ref == "u-manager"


def test_the_manager_never_receives_their_own_completion(
    directory: StubDirectory,
) -> None:
    _, enrollment = graph(
        user_ref="u-manager", actor="u-manager", status="completed", completed_at=timezone.now()
    )

    dispatch(
        DomainEvent(
            name=handlers.ENROLLMENT_COMPLETED,
            organization_id=ORG,
            payload={"enrollment_id": str(enrollment.pk), "user_ref": "u-manager"},
        )
    )

    assert not NotificationLog.objects.filter(kind=NotificationLog.Kind.LEARNER_COMPLETED).exists()


def test_pending_rows_are_bounded_by_the_attempt_cap() -> None:
    make_notification(ORG, dedupe_key="a:1", attempt_count=0)
    make_notification(ORG, dedupe_key="a:2", attempt_count=3)
    make_notification(
        ORG,
        dedupe_key="a:3",
        channel="in_app",
        status=NotificationLog.Status.SENT,
        sent_at=timezone.now(),
    )

    keys = {row.dedupe_key for row in service.pending()}
    assert keys == {"a:1"}
