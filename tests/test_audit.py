"""T-012 acceptance: ``audit.record`` and the append-only trigger.

The service is tested where it will be used — inside a caller's transaction — so a rollback has
to leave nothing behind, and the trigger is tested with queryset writes that bypass the model's
own guard.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from django.db import DatabaseError, transaction

from academy.audit import AuditError, record
from academy.models import AuditEvent

pytestmark = pytest.mark.django_db

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
OTHER_ORG = UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11")


def test_a_record_lands_in_the_caller_organization() -> None:
    event = record(
        organization_id=ORG,
        actor_ref="u-42",
        action="course.published",
        object_type="Course",
        object_id="c-1",
        metadata={"course_id": "c-1", "version_number": 3},
    )

    assert event.event_id is not None
    assert AuditEvent.objects.for_org(ORG).filter(event_id=event.event_id).count() == 1
    assert AuditEvent.objects.for_org(OTHER_ORG).count() == 0
    assert event.metadata == {"course_id": "c-1", "version_number": 3}
    assert event.occurred_at is not None
    assert str(event) == "course.published Course:c-1"


def test_the_system_may_be_the_actor_and_metadata_defaults_to_empty() -> None:
    event = record(
        organization_id=ORG,
        actor_ref="system",
        action="enrollment.completed_override",
        object_type="Enrollment",
        object_id=str(uuid4()),
    )

    assert event.metadata == {}


def test_a_record_disappears_with_its_transaction() -> None:
    with pytest.raises(RuntimeError), transaction.atomic():
        record(
            organization_id=ORG,
            actor_ref="u-42",
            action="grant.created",
            object_type="PermissionGrant",
            object_id="g-1",
        )
        raise RuntimeError("the caller rolled back")

    assert AuditEvent.objects.count() == 0


@pytest.mark.parametrize(
    "call",
    [
        {"organization_id": "not-a-uuid"},
        {"actor_ref": ""},
        {"actor_ref": " u-42"},
        {"actor_ref": "u" * 65},
        {"action": "Published"},
        {"action": "course"},
        {"object_type": "Course:1"},
        {"object_id": ""},
    ],
)
def test_a_malformed_call_is_refused(call: dict[str, str]) -> None:
    kwargs: dict[str, object] = {
        "organization_id": ORG,
        "actor_ref": "u-42",
        "action": "course.published",
        "object_type": "Course",
        "object_id": "c-1",
    }
    kwargs.update(call)

    with pytest.raises(AuditError):
        record(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "metadata",
    [
        {"display_name": "Example Employee"},
        {"email": "person@example.test"},
        {"notes": None},
        {"Course-id": "c-1"},
        {"course": {"id": "c-1"}},
        {"ids": [1, {"id": 2}]},
    ],
)
def test_metadata_carries_ids_only(metadata: dict[str, object]) -> None:
    with pytest.raises(AuditError):
        record(
            organization_id=ORG,
            actor_ref="u-42",
            action="course.created",
            object_type="Course",
            object_id="c-1",
            metadata=metadata,
        )


def test_a_repeated_event_id_is_idempotent() -> None:
    event_id = uuid4()
    first = record(
        organization_id=ORG,
        actor_ref="u-42",
        action="course.created",
        object_type="Course",
        object_id="c-1",
        event_id=event_id,
    )
    second = record(
        organization_id=ORG,
        actor_ref="u-42",
        action="course.created",
        object_type="Course",
        object_id="c-1",
        event_id=event_id,
    )

    assert first.pk == second.pk
    assert AuditEvent.objects.filter(event_id=event_id).count() == 1


def test_a_reused_event_id_for_another_action_is_refused() -> None:
    event_id = uuid4()
    record(
        organization_id=ORG,
        actor_ref="u-42",
        action="course.created",
        object_type="Course",
        object_id="c-1",
        event_id=event_id,
    )

    with pytest.raises(AuditError):
        record(
            organization_id=ORG,
            actor_ref="u-42",
            action="course.archived",
            object_type="Course",
            object_id="c-1",
            event_id=event_id,
        )


def test_an_event_cannot_be_updated_in_the_database() -> None:
    event = record(
        organization_id=ORG,
        actor_ref="u-42",
        action="course.created",
        object_type="Course",
        object_id="c-1",
    )

    with pytest.raises(DatabaseError, match="audit_event_append_only"), transaction.atomic():
        AuditEvent.objects.filter(pk=event.pk).update(actor_ref="u-99")


def test_an_event_cannot_be_deleted_from_the_database() -> None:
    event = record(
        organization_id=ORG,
        actor_ref="u-42",
        action="course.created",
        object_type="Course",
        object_id="c-1",
    )

    with pytest.raises(DatabaseError, match="audit_event_append_only"), transaction.atomic():
        AuditEvent.objects.filter(pk=event.pk).delete()


def test_the_model_refuses_to_rewrite_or_delete_a_row() -> None:
    event = record(
        organization_id=ORG,
        actor_ref="u-42",
        action="course.created",
        object_type="Course",
        object_id="c-1",
    )
    event.actor_ref = "u-99"

    with pytest.raises(ValueError, match="append-only"):
        event.save()
    with pytest.raises(ValueError, match="append-only"):
        event.delete()
