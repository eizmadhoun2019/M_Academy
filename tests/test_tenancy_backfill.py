"""T-026 CP2 acceptance: map legacy refs, backfill the FKs, reconcile and stop on a guess.

The identity file here is synthetic; no real address is invented or imported by the tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from django.core.management import CommandError, call_command
from django.db import DatabaseError, transaction
from django.utils import timezone
from factories import (
    make_assignment,
    make_audit,
    make_completion,
    make_course,
    make_enrollment,
    make_grant,
    make_media,
    make_notification,
    make_reminder,
    make_suspension,
    make_version,
)

from academy.models import (
    AccessSuspension,
    Assignment,
    AuditEvent,
    CompletionRecord,
    Course,
    Department,
    Enrollment,
    MediaAsset,
    Membership,
    NotificationLog,
    PermissionGrant,
    ReminderLog,
    User,
)


def write_identities(path: Path, rows: list[tuple[str, str, str]]) -> Path:
    lines = ["legacy_user_ref,email,display_name"]
    lines.extend(",".join(row) for row in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_backfill(identities: Path, report: Path, *extra: str) -> dict[str, Any]:
    call_command(
        "backfill_tenancy",
        "--identities",
        str(identities),
        "--report",
        str(report),
        *extra,
        verbosity=0,
    )
    return json.loads(report.read_text(encoding="utf-8"))


@pytest.mark.django_db
def test_dry_run_reports_a_full_plan_and_writes_nothing(
    org_id: UUID, enrollment: Enrollment, tmp_path: Path
) -> None:
    identities = write_identities(
        tmp_path / "identities.csv", [("u-learner", "learner@example.com", "Learner")]
    )

    report = run_backfill(identities, tmp_path / "report.json", "--dry-run")

    assert User.objects.count() == 0
    assert Department.objects.count() == 0
    assert Membership.objects.count() == 0
    assert Enrollment.objects.get(pk=enrollment.pk).membership_id is None
    assert report["dry_run"] is True
    assert report["ok"] is True
    assert report["accounts"]["planned"] == 1
    assert report["memberships"]["planned"] == 1
    assert report["links"]["enrollment_membership"]["filled"] == 1
    assert report["links"]["enrollment_membership"]["unresolved"] == 0


@pytest.mark.django_db
def test_backfill_attaches_every_row_and_reconciles_the_counts(
    org_id: UUID, tmp_path: Path
) -> None:
    course = make_course(org_id, owner_department_ref="dep-a", created_by_ref="u-author")
    version = make_version(
        org_id,
        course=course,
        created_by_ref="u-author",
        published_by_ref="u-manager",
    )
    media = make_media(org_id, created_by_ref="u-author")
    assignment = make_assignment(
        org_id,
        course=course,
        target_type=Assignment.TargetType.DEPARTMENT,
        target_ref="dep-b",
        assigned_by_ref="u-manager",
    )
    enrollment = make_enrollment(org_id, course=course, version=version)
    completion = make_completion(org_id, enrollment=enrollment)
    reminder = make_reminder(org_id, enrollment=enrollment)
    notification = make_notification(org_id)
    organization_grant = make_grant(org_id)
    department_grant = make_grant(
        org_id,
        scope_type=PermissionGrant.Scope.DEPARTMENT,
        scope_ref="dep-a",
    )
    suspension = make_suspension(org_id)
    audit = make_audit(org_id)
    system_audit = make_audit(org_id, actor_ref="system:scheduler")
    identities = write_identities(
        tmp_path / "identities.csv",
        [
            ("u-learner", "learner@example.com", "Learner"),
            ("u-author", "author@example.com", "Author"),
            ("u-manager", "manager@example.com", "Manager"),
            ("u-42", "grantee@example.com", "Grantee"),
            ("u-suspended", "suspended@example.com", "Suspended"),
            ("u-admin", "admin@example.com", "Admin"),
        ],
    )

    report = run_backfill(identities, tmp_path / "report.json")

    enrollment = Enrollment.objects.get(pk=enrollment.pk)
    assert enrollment.membership is not None
    assert enrollment.membership.user.legacy_ref == "u-learner"
    completion = CompletionRecord.objects.get(pk=completion.pk)
    assert completion.membership_id == enrollment.membership_id
    assert completion.user_id == enrollment.membership.user_id
    assert ReminderLog.objects.get(pk=reminder.pk).recipient_membership_id == (
        enrollment.membership_id
    )
    assert NotificationLog.objects.get(pk=notification.pk).recipient_user_id == (
        enrollment.membership.user_id
    )
    course = Course.objects.get(pk=course.pk)
    assert course.owner_department is not None
    assert course.owner_department.legacy_ref == "dep-a"
    assert course.created_by is not None
    assert course.created_by.user.legacy_ref == "u-author"
    media = MediaAsset.objects.get(pk=media.pk)
    assert media.created_by is not None
    assert media.created_by.user.legacy_ref == "u-author"
    assignment = Assignment.objects.get(pk=assignment.pk)
    assert assignment.target_department is not None
    assert assignment.target_department.legacy_ref == "dep-b"
    assert assignment.assigned_by is not None
    assert assignment.assigned_by.user.legacy_ref == "u-manager"
    assert PermissionGrant.objects.get(pk=organization_grant.pk).membership_id == (
        Membership.objects.get(user__legacy_ref="u-42").id
    )
    assert PermissionGrant.objects.get(pk=department_grant.pk).scope_department_id == (
        Department.objects.get(legacy_ref="dep-a").id
    )
    suspension = AccessSuspension.objects.get(pk=suspension.pk)
    assert suspension.membership is not None
    assert suspension.membership.user.legacy_ref == "u-suspended"
    assert suspension.suspended_by is not None
    assert suspension.suspended_by.user.legacy_ref == "u-admin"
    audit = AuditEvent.objects.get(pk=audit.pk)
    assert audit.actor_user_id == User.objects.get(legacy_ref="u-manager").id
    assert audit.actor_membership_id == Membership.objects.get(user__legacy_ref="u-manager").id
    system_audit = AuditEvent.objects.get(pk=system_audit.pk)
    assert system_audit.actor_user_id is None
    assert system_audit.actor_membership_id is None
    assert report["links"]["audit_actor_user"]["system"] == 1

    assert report["ok"] is True
    assert report["accounts"]["created"] == 6
    assert report["accounts"]["placeholder_email"] == 0
    assert report["memberships"]["created"] == 6
    assert report["departments"]["distinct_refs"] == 2
    assert report["departments"]["created"] == 2
    assert report["invariants"] == {
        "users_with_more_than_one_membership": 0,
        "accounts_with_memberships_in_two_companies": 0,
        "required_unresolved_rows": 0,
    }
    assert report["deferred"]["assignment_role_targets"] == 0


@pytest.mark.django_db
def test_a_second_run_is_a_no_op(org_id: UUID, enrollment: Enrollment, tmp_path: Path) -> None:
    identities = write_identities(
        tmp_path / "identities.csv", [("u-learner", "learner@example.com", "Learner")]
    )
    first = run_backfill(identities, tmp_path / "first.json")
    second = run_backfill(identities, tmp_path / "second.json")

    assert first["accounts"]["created"] == 1
    assert second["accounts"]["created"] == 0
    assert second["memberships"]["created"] == 0
    assert second["departments"]["created"] == 0
    assert all(link["filled"] == 0 for link in second["links"].values())
    assert User.objects.filter(legacy_ref="u-learner").count() == 1
    assert Membership.objects.filter(user__legacy_ref="u-learner").count() == 1
    assert second["ok"] is True


@pytest.mark.django_db
def test_an_unknown_learner_ref_aborts_without_touching_a_row(
    enrollment: Enrollment, tmp_path: Path
) -> None:
    identities = write_identities(tmp_path / "identities.csv", [])
    report_path = tmp_path / "report.json"

    with pytest.raises(CommandError):
        run_backfill(identities, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is False
    assert any("no account in the identity file" in error for error in report["errors"])
    assert User.objects.count() == 0
    assert Enrollment.objects.get(pk=enrollment.pk).membership_id is None


@pytest.mark.django_db
def test_one_mailbox_cannot_become_two_accounts(tmp_path: Path) -> None:
    identities = write_identities(
        tmp_path / "identities.csv",
        [
            ("u-one", "shared@example.com", "One"),
            ("u-two", "shared@example.com", "Two"),
        ],
    )

    with pytest.raises(CommandError, match="one mailbox cannot be two accounts"):
        run_backfill(identities, tmp_path / "report.json")

    assert User.objects.count() == 0


@pytest.mark.django_db
def test_a_filled_completion_link_cannot_be_rewritten(
    org_id: UUID, enrollment: Enrollment, tmp_path: Path
) -> None:
    completion = make_completion(org_id, enrollment=enrollment)
    identities = write_identities(
        tmp_path / "identities.csv", [("u-learner", "learner@example.com", "Learner")]
    )
    run_backfill(identities, tmp_path / "report.json")
    completion = CompletionRecord.objects.get(pk=completion.pk)
    assert completion.membership_id is not None
    other_user = User.objects.create(email="other@example.com", display_name="Other")
    other = Membership.objects.create(
        organization_id=org_id,
        user=other_user,
        status=Membership.Status.ACTIVE,
        joined_at=timezone.now(),
    )

    with pytest.raises(DatabaseError, match="completion_record_immutable"), transaction.atomic():
        CompletionRecord.objects.filter(pk=completion.pk).update(membership=other)


@pytest.mark.django_db
def test_a_filled_audit_actor_cannot_be_rewritten(
    org_id: UUID, enrollment: Enrollment, tmp_path: Path
) -> None:
    audit = make_audit(org_id, actor_ref="u-learner")
    identities = write_identities(
        tmp_path / "identities.csv", [("u-learner", "learner@example.com", "Learner")]
    )
    run_backfill(identities, tmp_path / "report.json")
    audit = AuditEvent.objects.get(pk=audit.pk)
    assert audit.actor_user_id is not None
    other_user = User.objects.create(email="other@example.com", display_name="Other")
    Membership.objects.create(
        organization_id=org_id,
        user=other_user,
        status=Membership.Status.ACTIVE,
        joined_at=timezone.now(),
    )

    with pytest.raises(DatabaseError, match="audit_event_append_only"), transaction.atomic():
        AuditEvent.objects.filter(pk=audit.pk).update(actor_user_id=other_user.id)


@pytest.mark.django_db
def test_an_account_without_an_address_is_created_disabled_and_flagged(
    enrollment: Enrollment, tmp_path: Path
) -> None:
    identities = write_identities(tmp_path / "identities.csv", [("u-learner", "", "Learner Name")])

    report = run_backfill(identities, tmp_path / "report.json")

    user = User.objects.get(legacy_ref="u-learner")
    assert user.status == User.Status.DEACTIVATED
    assert user.is_email_verified is False
    assert user.must_set_email is True
    assert user.email.startswith("pending+")
    assert user.email.endswith("@invalid.masheed")
    assert user.display_name == "Learner Name"
    assert user.memberships.get().status == Membership.Status.ACTIVE
    assert report["accounts"]["placeholder_email"] == 1
    assert report["ok"] is True


@pytest.mark.django_db
def test_an_unknown_actor_stays_null_and_is_only_reported(
    org_id: UUID, enrollment: Enrollment, tmp_path: Path
) -> None:
    course = make_course(org_id, created_by_ref="u-ghost")
    identities = write_identities(
        tmp_path / "identities.csv", [("u-learner", "learner@example.com", "Learner")]
    )

    report = run_backfill(identities, tmp_path / "report.json")

    course = Course.objects.get(pk=course.pk)
    assert course.created_by_id is None
    assert report["links"]["course_created_by"]["unresolved"] == 2
    assert report["links"]["course_created_by"]["unresolved_refs"] == [
        "u-author",
        "u-ghost",
    ]
    assert report["ok"] is True


@pytest.mark.django_db
def test_an_existing_account_is_never_adopted_by_email(tmp_path: Path) -> None:
    existing = User.objects.create(email="taken@example.com", display_name="Existing")
    identities = write_identities(
        tmp_path / "identities.csv", [("u-learner", "taken@example.com", "Learner")]
    )

    with pytest.raises(CommandError):
        run_backfill(identities, tmp_path / "report.json")

    assert User.objects.get(pk=existing.pk).legacy_ref is None
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_an_empty_department_ref_aborts_instead_of_guessing(org_id: UUID, tmp_path: Path) -> None:
    make_assignment(
        org_id,
        target_type=Assignment.TargetType.DEPARTMENT,
        target_ref=" ",
    )
    identities = write_identities(
        tmp_path / "identities.csv", [("u-manager", "manager@example.com", "Manager")]
    )
    report_path = tmp_path / "report.json"

    with pytest.raises(CommandError):
        run_backfill(identities, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert any("empty department ref" in error for error in report["errors"])
    assert Department.objects.count() == 0
