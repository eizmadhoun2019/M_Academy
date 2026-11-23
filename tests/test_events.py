"""T-005 acceptance: events fire only after commit, once, and reach every subscriber."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from django.db import transaction

from academy.events import (
    DomainEvent,
    clear_handlers,
    emit_on_commit,
    handlers_for,
    subscribe,
    unsubscribe,
)

pytestmark = pytest.mark.django_db(transaction=True)

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
OTHER_ORG = UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11")


@pytest.fixture(autouse=True)
def _clean_handlers() -> Iterator[None]:
    clear_handlers()
    yield
    clear_handlers()


class Recorder:
    """A handler that remembers what it was given."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def __call__(self, event: DomainEvent) -> None:
        self.events.append(event)


def test_an_event_waits_for_the_outermost_commit() -> None:
    recorder = Recorder()
    subscribe("course.published", recorder)

    with transaction.atomic():
        with transaction.atomic():
            emit_on_commit("course.published", organization_id=ORG, actor_ref="u-10")
        assert recorder.events == []
    assert len(recorder.events) == 1


def test_a_rolled_back_transaction_dispatches_nothing() -> None:
    recorder = Recorder()
    subscribe("course.published", recorder)

    with pytest.raises(RuntimeError), transaction.atomic():
        emit_on_commit("course.published", organization_id=ORG)
        raise RuntimeError("the write failed")

    assert recorder.events == []


def test_an_event_outside_a_transaction_is_dispatched_immediately() -> None:
    recorder = Recorder()
    subscribe("media.ready", recorder)

    emit_on_commit("media.ready", organization_id=ORG, payload={"asset_id": "m-1"})

    assert len(recorder.events) == 1
    assert recorder.events[0].payload == {"asset_id": "m-1"}


def test_the_event_carries_what_the_caller_supplied() -> None:
    recorder = Recorder()
    subscribe("enrollment.completed", recorder)
    moment = datetime(2026, 11, 23, 9, 30, tzinfo=UTC)

    with transaction.atomic():
        emitted = emit_on_commit(
            "enrollment.completed",
            organization_id=ORG,
            actor_ref="u-42",
            payload={"enrollment_id": "e-79"},
            occurred_at=moment,
        )

    delivered = recorder.events[0]
    assert delivered == emitted
    assert delivered.event_id == emitted.event_id
    assert delivered.organization_id == ORG
    assert delivered.actor_ref == "u-42"
    assert delivered.occurred_at == moment


def test_every_subscriber_receives_the_event_in_order() -> None:
    calls: list[str] = []

    subscribe("assignment.cancelled", lambda event: calls.append("first"))
    subscribe("assignment.cancelled", lambda event: calls.append("second"))

    with transaction.atomic():
        emit_on_commit("assignment.cancelled", organization_id=ORG)

    assert calls == ["first", "second"]


def test_an_unsubscribed_handler_is_not_called() -> None:
    recorder = Recorder()
    subscribe("grant.created", recorder)
    unsubscribe("grant.created", recorder)

    assert handlers_for("grant.created") == ()
    with transaction.atomic():
        emit_on_commit("grant.created", organization_id=ORG)

    assert recorder.events == []


def test_a_handler_only_sees_its_own_event_name() -> None:
    published = Recorder()
    created = Recorder()
    subscribe("course.published", published)
    subscribe("course.created", created)

    with transaction.atomic():
        emit_on_commit("course.published", organization_id=ORG)

    assert len(published.events) == 1
    assert created.events == []


def test_a_failing_handler_is_logged_and_does_not_stop_the_next(
    caplog: pytest.LogCaptureFixture,
) -> None:
    recorder = Recorder()

    def explode(event: DomainEvent) -> None:
        raise RuntimeError("handler is broken")

    subscribe("course.archived", explode)
    subscribe("course.archived", recorder)

    with caplog.at_level(logging.ERROR, logger="academy.events"), transaction.atomic():
        emit_on_commit("course.archived", organization_id=ORG)

    assert len(recorder.events) == 1
    assert "domain event handler failed" in caplog.text


def test_a_handler_may_emit_another_event() -> None:
    follow_up = Recorder()
    subscribe("version.published", follow_up)

    def on_course_published(event: DomainEvent) -> None:
        emit_on_commit(
            "version.published",
            organization_id=event.organization_id,
            payload={"course_id": "c-1"},
        )

    subscribe("course.published", on_course_published)

    with transaction.atomic():
        emit_on_commit("course.published", organization_id=ORG)

    assert len(follow_up.events) == 1
    assert follow_up.events[0].payload == {"course_id": "c-1"}


def test_the_event_is_frozen_and_its_payload_cannot_be_mutated() -> None:
    event = DomainEvent(name="course.created", organization_id=ORG, payload={"course_id": "c-1"})

    with pytest.raises(AttributeError):
        event.name = "course.archived"  # type: ignore[misc]
    payload = event.payload
    with pytest.raises(TypeError):
        payload["course_id"] = "other"  # type: ignore[index]


@pytest.mark.parametrize(
    "name", ["", "course", "Course.Published", "course..published", ".x", "x."]
)
def test_an_event_name_must_be_area_dot_action(name: str) -> None:
    with pytest.raises(ValueError):
        DomainEvent(name=name, organization_id=ORG)


def test_actor_ref_must_be_a_short_non_empty_string() -> None:
    with pytest.raises(ValueError):
        DomainEvent(name="course.created", organization_id=ORG, actor_ref="   ")
    with pytest.raises(ValueError):
        DomainEvent(name="course.created", organization_id=ORG, actor_ref="u" * 65)


def test_the_organization_must_be_a_uuid() -> None:
    with pytest.raises(ValueError):
        DomainEvent(name="course.created", organization_id="25498ed9")  # type: ignore[arg-type]


def test_the_payload_must_be_json_serializable() -> None:
    with pytest.raises(ValueError):
        DomainEvent(name="course.created", organization_id=ORG, payload={"bad": object()})


def test_a_naive_timestamp_is_refused() -> None:
    with pytest.raises(ValueError):
        DomainEvent(
            name="course.created",
            organization_id=ORG,
            occurred_at=datetime(2026, 11, 23, 9, 30),  # noqa: DTZ001 - the point of the test
        )


def test_as_dict_is_plain_data() -> None:
    event = DomainEvent(name="course.created", organization_id=ORG, payload={"course_id": "c-1"})

    data = event.as_dict()

    assert data["name"] == "course.created"
    assert data["organization_id"] == str(ORG)
    assert data["event_id"] == str(event.event_id)
    assert data["payload"] == {"course_id": "c-1"}


def test_two_events_have_different_ids() -> None:
    first = DomainEvent(name="course.created", organization_id=ORG)
    second = DomainEvent(name="course.created", organization_id=OTHER_ORG)

    assert first.event_id != second.event_id
    assert first.event_id != uuid4()
