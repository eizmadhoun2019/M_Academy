"""Count-only audit of legacy data awaiting the tenancy mapping (T-026 CP2 evidence).

Answers the reconciliation question of ``docs/migration-h1.5.md`` §8 with numbers only: the
command selects ``COUNT`` and ``DISTINCT`` values and never prints a name, an e-mail, a reference
value or any other row content. Nothing is written, so it is safe on any environment, including a
restored production dump before cutover.
"""

from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import CharField, Count, ForeignKey, Model

from academy.models import (
    AccessSuspension,
    Assignment,
    AuditEvent,
    CompletionRecord,
    Course,
    CourseVersion,
    Department,
    Enrollment,
    HubWebhookEvent,
    Lesson,
    LessonProgress,
    MediaAsset,
    Membership,
    NotificationLog,
    Organization,
    PermissionGrant,
    Quiz,
    QuizAttempt,
    ReminderLog,
    Section,
    User,
)

#: Nullable links the CP2 backfill fills (``docs/migration-h1.5.md`` §4 M3). Department parents
#: and invitation actors are deliberately absent: they are not migration targets.
LEGACY_LINKS = frozenset(
    {
        "owner_department",
        "created_by",
        "published_by",
        "target_membership",
        "target_department",
        "assigned_by",
        "membership",
        "recipient_membership",
        "recipient_user",
        "suspended_by",
        "lifted_by",
        "scope_department",
        "granted_by",
        "actor_user",
        "actor_membership",
        "user",
    }
)

TENANT_MODELS: tuple[type[Model], ...] = (
    Course,
    CourseVersion,
    Section,
    Lesson,
    MediaAsset,
    Assignment,
    Enrollment,
    LessonProgress,
    CompletionRecord,
    Quiz,
    QuizAttempt,
    ReminderLog,
    NotificationLog,
    AuditEvent,
    PermissionGrant,
    AccessSuspension,
    HubWebhookEvent,
)


def _null_links(model: type[Model]) -> dict[str, int]:
    """Legacy rows of one table whose migration link is still ``NULL``, per field."""
    missing: dict[str, int] = {}
    for field in model._meta.get_fields():
        if not isinstance(field, ForeignKey) or not field.null:
            continue
        if field.name not in LEGACY_LINKS:
            continue
        count = model._default_manager.filter(**{f"{field.name}__isnull": True}).count()
        if count:
            missing[field.name] = count
    return missing


def _distinct_refs(model: type[Model]) -> tuple[dict[str, int], set[str]]:
    """Distinct non-empty legacy references per ``*_ref`` column (values stay in memory)."""
    counts: dict[str, int] = {}
    values: set[str] = set()
    for field in model._meta.fields:
        if not isinstance(field, CharField) or not field.name.endswith("_ref"):
            continue
        rows = (
            model._default_manager.exclude(**{field.name: ""})
            .exclude(**{f"{field.name}__isnull": True})
            .exclude(**{field.name: "system"})
        )
        counts[field.name] = rows.values(field.name).distinct().count()
        values.update(str(value) for value in rows.values_list(field.name, flat=True))
    return counts, values


def audit() -> dict[str, Any]:
    """The reconciliation report: counts only, never row content."""
    tenancy = {
        "Organization": Organization.objects.count(),
        "Organization.active": Organization.objects.filter(
            status=Organization.Status.ACTIVE
        ).count(),
        "User": User.objects.count(),
        "User.with_legacy_ref": User.objects.exclude(legacy_ref__isnull=True)
        .exclude(legacy_ref="")
        .count(),
        "User.must_set_email": User.objects.filter(must_set_email=True).count(),
        "Department": Department.objects.count(),
        "Department.with_legacy_ref": Department.objects.exclude(legacy_ref__isnull=True)
        .exclude(legacy_ref="")
        .count(),
        "Membership": Membership.objects.count(),
        "Membership.active": Membership.objects.filter(status=Membership.Status.ACTIVE).count(),
    }

    tables: dict[str, dict[str, Any]] = {}
    refs_by_table: dict[str, dict[str, int]] = {}
    all_refs: set[str] = set()
    for model in TENANT_MODELS:
        tables[model.__name__] = {
            "rows": model._default_manager.count(),
            "null_links": _null_links(model),
        }
        counts, values = _distinct_refs(model)
        if counts:
            refs_by_table[model.__name__] = counts
            all_refs |= values

    integrity = {
        "users_with_more_than_one_membership": Membership.objects.values("user_id")
        .annotate(rows=Count("id"))
        .filter(rows__gt=1)
        .count(),
        "users_in_more_than_one_company": Membership.objects.values("user_id")
        .annotate(companies=Count("organization_id", distinct=True))
        .filter(companies__gt=1)
        .count(),
        "tenant_rows_total": sum(entry["rows"] for entry in tables.values()),
        "rows_missing_a_link": sum(
            count for entry in tables.values() for count in entry["null_links"].values()
        ),
    }
    return {
        "tenancy": tenancy,
        "tables": tables,
        "distinct_refs": {
            "total": len(all_refs),
            "per_table": {name: sum(counts.values()) for name, counts in refs_by_table.items()},
            "per_field": {name: counts for name, counts in refs_by_table.items() if counts},
        },
        "integrity": integrity,
        "needs_migration": bool(integrity["tenant_rows_total"] or integrity["rows_missing_a_link"]),
    }


class Command(BaseCommand):
    help = "Report, as counts only, how much legacy data still needs the tenancy mapping."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--json", action="store_true", help="Print the report as one JSON object"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        report = audit()
        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
            return

        tenancy = report["tenancy"]
        self.stdout.write(
            f"organizations: {tenancy['Organization']} "
            f"(active {tenancy['Organization.active']}), "
            f"accounts: {tenancy['User']} (legacy refs {tenancy['User.with_legacy_ref']}), "
            f"memberships: {tenancy['Membership']} (active {tenancy['Membership.active']})"
        )
        for name, entry in report["tables"].items():
            if not entry["rows"] and not entry["null_links"]:
                continue
            links = ", ".join(f"{field}={count}" for field, count in entry["null_links"].items())
            detail = f" — missing links: {links}" if links else ""
            self.stdout.write(f"{name}: {entry['rows']} row(s){detail}")
        refs = report["distinct_refs"]
        self.stdout.write(
            f"distinct legacy references: {refs['total']} across {len(refs['per_table'])} table(s)"
        )
        integrity = report["integrity"]
        self.stdout.write(
            "duplicate memberships: "
            f"{integrity['users_with_more_than_one_membership']}, "
            "accounts in more than one company: "
            f"{integrity['users_in_more_than_one_company']}"
        )
        if report["needs_migration"]:
            self.stdout.write(
                "legacy data requiring migration: present — do not cut over without the mapping"
            )
        else:
            self.stdout.write("legacy data requiring migration: none")
