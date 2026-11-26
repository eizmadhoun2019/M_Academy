"""Map legacy refs onto companies, departments, accounts and memberships (T-026 CP2).

Implements ``docs/migration-h1.5.md`` §4 **M2 (seed and map)** and **M3 (backfill)**:

* departments come from every distinct ``department_ref`` the tenant tables still hold;
* accounts and their single membership come only from the owner-provided CSV
  (``legacy_user_ref,email,display_name``) — an address is never guessed;
* an account without an address keeps a non-deliverable placeholder and ``must_set_email``,
  so it exists for its history but cannot sign in (T-027 sets a real address);
* the new foreign keys are filled in batches of ``--batch-size`` rows, one transaction per
  batch, and a second run changes nothing;
* every unresolved required ref aborts the run: the command never attaches a row by guess.

The report is data, not a model (M2): it carries the counts that reconcile distinct legacy
refs against created rows, plus the duplicate-membership queries the cutover must see at zero.
Unknown **actor** refs (``created_by_ref`` and friends) are reported and stay ``NULL``: the
legacy text remains in its own column for audit reconstruction, exactly as §3 says.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, Model, QuerySet
from django.utils import timezone

from academy.models import (
    AccessSuspension,
    Assignment,
    AuditEvent,
    CompletionRecord,
    Course,
    CourseVersion,
    Department,
    Enrollment,
    MediaAsset,
    Membership,
    NotificationLog,
    Organization,
    PermissionGrant,
    ReminderLog,
    User,
)

IDENTITY_COLUMNS = ("legacy_user_ref", "email", "display_name")
DEFAULT_BATCH_SIZE = 5_000
PLACEHOLDER_DOMAIN = "invalid.masheed"
SYSTEM_REFS = ("system",)


@dataclass(frozen=True)
class Identity:
    """One row of the owner-provided identity file."""

    legacy_ref: str
    email: str
    display_name: str


@dataclass(frozen=True)
class LinkSpec:
    """One nullable target column and the legacy column that names its owner."""

    name: str
    model: type[Model]
    source: str
    target: str
    mapping: str
    required: bool = False
    filters: Mapping[str, Any] = field(default_factory=dict)
    allow_system: bool = False


def read_identities(path: str | Path) -> tuple[list[Identity], list[str]]:
    """Parse the identity CSV strictly; return rows plus every problem found."""
    errors: list[str] = []
    identities: list[Identity] = []
    seen_refs: dict[str, int] = {}
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError as error:
        raise CommandError(f"cannot read the identity file: {error}") from error

    reader = csv.DictReader(io.StringIO(text))
    header = tuple((name or "").strip() for name in reader.fieldnames or ())
    if header != IDENTITY_COLUMNS:
        raise CommandError(
            f"identity file header must be {','.join(IDENTITY_COLUMNS)}, got {','.join(header)}"
        )
    for line, raw in enumerate(reader, start=2):
        ref = (raw.get("legacy_user_ref") or "").strip()
        email = (raw.get("email") or "").strip().lower()
        name = (raw.get("display_name") or "").strip()
        if not ref:
            errors.append(f"line {line}: legacy_user_ref is blank")
            continue
        if len(ref) > 64:
            errors.append(f"line {line}: legacy_user_ref {ref!r} exceeds 64 characters")
            continue
        if ref in seen_refs:
            errors.append(f"line {line}: legacy_user_ref {ref!r} repeats line {seen_refs[ref]}")
            continue
        if len(name) > 150:
            errors.append(f"line {line}: display_name for {ref!r} exceeds 150 characters")
            continue
        if email:
            if len(email) > 254:
                errors.append(f"line {line}: e-mail for {ref!r} exceeds 254 characters")
                continue
            try:
                validate_email(email)
            except ValidationError:
                errors.append(f"line {line}: e-mail for {ref!r} is not valid")
                continue
        seen_refs[ref] = line
        identities.append(Identity(legacy_ref=ref, email=email, display_name=name))

    emails: dict[str, str] = {}
    for identity in identities:
        if not identity.email:
            continue
        owner = emails.get(identity.email)
        if owner is not None and owner != identity.legacy_ref:
            errors.append(
                f"e-mail {identity.email!r} is shared by {owner!r} and "
                f"{identity.legacy_ref!r}: one mailbox cannot be two accounts"
            )
        emails[identity.email] = identity.legacy_ref
    return identities, errors


def _chunks(ids: Sequence[UUID], size: int) -> Iterator[Sequence[UUID]]:
    for start in range(0, len(ids), size):
        yield ids[start : start + size]


def _clean(value: Any) -> str:
    return (value or "").strip()


def _is_system(ref: str) -> bool:
    lowered = ref.lower()
    return any(lowered == prefix or lowered.startswith(f"{prefix}:") for prefix in SYSTEM_REFS)


class TenancyBackfill:
    """One mapping/backfill run; ``run()`` returns the JSON-serialisable report."""

    def __init__(
        self,
        *,
        organization_id: UUID,
        identities: Sequence[Identity],
        dry_run: bool,
        batch_size: int,
    ) -> None:
        self.organization_id = organization_id
        self.identities = list(identities)
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.user_ids: dict[str, UUID] = {}
        self.membership_ids: dict[str, UUID] = {}
        self.department_ids: dict[str, UUID] = {}
        self.planned_users: set[str] = set()
        self.planned_departments: set[str] = set()
        self.errors: list[str] = []
        self.unresolved_required_rows = 0
        self.report: dict[str, Any] = {}

    # -- preflight -------------------------------------------------------------------------
    def _check_company(self) -> None:
        if not Organization.objects.filter(id=self.organization_id).exists():
            self.errors.append(
                f"organization {self.organization_id} does not exist; run the migrations first"
            )

    def _load_existing(self) -> None:
        self.user_ids = {
            ref: user_id
            for ref, user_id in User.objects.exclude(legacy_ref__isnull=True).values_list(
                "legacy_ref", "id"
            )
            if ref
        }
        self.department_ids = {
            ref: department_id
            for ref, department_id in Department.objects.filter(
                organization_id=self.organization_id
            )
            .exclude(legacy_ref__isnull=True)
            .values_list("legacy_ref", "id")
            if ref
        }
        self.membership_ids = {
            ref: membership_id
            for ref, membership_id in Membership.objects.filter(
                organization_id=self.organization_id, user_id__in=list(self.user_ids.values())
            ).values_list("user__legacy_ref", "id")
            if ref
        }

    def _validate(self) -> None:
        for identity in self.identities:
            if identity.legacy_ref in self.user_ids:
                continue
            if identity.email:
                existing = User.objects.filter(email=identity.email).first()
                if existing is not None and existing.legacy_ref != identity.legacy_ref:
                    self.errors.append(
                        f"e-mail {identity.email!r} already belongs to account {existing.id}; "
                        f"refusing to attach it to {identity.legacy_ref!r}"
                    )
            self.planned_users.add(identity.legacy_ref)

        known_users = set(self.user_ids) | self.planned_users
        required_refs, blank_user_refs = self._collect_user_refs()
        missing = sorted(required_refs - known_users)
        if missing:
            shown = ", ".join(repr(ref) for ref in missing[:10])
            more = "" if len(missing) <= 10 else f" and {len(missing) - 10} more"
            self.errors.append(
                f"{len(missing)} legacy user ref(s) have no account in the identity file: "
                f"{shown}{more}. Add them to the CSV; an address is never guessed."
            )
        if blank_user_refs:
            self.errors.append(
                f"{blank_user_refs} row(s) name an empty learner/recipient ref; "
                "the row cannot be attached and cutover stops"
            )

        required_departments, blank_department_refs = self._collect_department_refs()
        if blank_department_refs:
            self.errors.append(
                f"{blank_department_refs} row(s) name an empty department ref; "
                "the row cannot be attached and cutover stops"
            )
        self.planned_departments = required_departments - set(self.department_ids)

        foreign_memberships = (
            Membership.objects.filter(user_id__in=list(self.user_ids.values()))
            .exclude(organization_id=self.organization_id)
            .count()
        )
        if foreign_memberships:
            self.errors.append(
                f"{foreign_memberships} mapped account(s) already belong to another company; "
                "one account holds at most one membership (D-043)"
            )

    def _collect_user_refs(self) -> tuple[set[str], int]:
        """Refs a row cannot be attached without, plus the count of blank ones."""
        lookups: list[tuple[type[Model], str, Mapping[str, Any]]] = [
            (Enrollment, "user_ref", {}),
            (CompletionRecord, "user_ref", {}),
            (ReminderLog, "recipient_ref", {}),
            (NotificationLog, "recipient_ref", {}),
            (Assignment, "target_ref", {"target_type": Assignment.TargetType.USER}),
            (PermissionGrant, "user_ref", {}),
            (AccessSuspension, "user_ref", {}),
        ]
        refs: set[str] = set()
        blank = 0
        for model, field_name, filters in lookups:
            for raw in (
                model._default_manager.filter(organization_id=self.organization_id, **filters)
                .values_list(field_name, flat=True)
                .iterator(chunk_size=self.batch_size)
            ):
                if raw is None:  # NULL means "not set" here, never an empty ref
                    continue
                ref = _clean(raw)
                if ref:
                    refs.add(ref)
                else:
                    blank += 1
        return refs, blank

    def _collect_department_refs(self) -> tuple[set[str], int]:
        refs: set[str] = set()
        blank = 0
        sources: list[tuple[type[Model], str, Mapping[str, Any]]] = [
            (Course, "owner_department_ref", {}),
            (Assignment, "target_ref", {"target_type": Assignment.TargetType.DEPARTMENT}),
            (PermissionGrant, "scope_ref", {"scope_type": PermissionGrant.Scope.DEPARTMENT}),
        ]
        for model, field_name, filters in sources:
            for raw in (
                model._default_manager.filter(organization_id=self.organization_id, **filters)
                .values_list(field_name, flat=True)
                .iterator(chunk_size=self.batch_size)
            ):
                if raw is None:  # NULL means "not set" here, never an empty ref
                    continue
                ref = _clean(raw)
                if ref:
                    refs.add(ref)
                else:
                    blank += 1
        return refs, blank

    # -- M2: seed and map ------------------------------------------------------------------
    def _create_departments(self) -> dict[str, int]:
        created = 0
        for ref in sorted(self.planned_departments):
            department = Department.objects.create(
                organization_id=self.organization_id,
                name_ar=ref,
                legacy_ref=ref,
            )
            self.department_ids[ref] = department.id
            created += 1
        return {"created": created, "existing": len(self.department_ids) - created}

    def _create_accounts(self) -> dict[str, int]:
        created = 0
        placeholders = 0
        for identity in self.identities:
            if identity.legacy_ref in self.user_ids:
                continue
            email = identity.email or (f"pending+{uuid.uuid4()}@{PLACEHOLDER_DOMAIN}")
            placeholders += 0 if identity.email else 1
            user = User.objects.create(
                email=email,
                display_name=identity.display_name or identity.legacy_ref,
                password=make_password(None),
                status=User.Status.DEACTIVATED,
                is_email_verified=False,
                must_set_email=not identity.email,
                legacy_ref=identity.legacy_ref,
            )
            self.user_ids[identity.legacy_ref] = user.id
            created += 1
        return {
            "created": created,
            "existing": len(self.user_ids) - created,
            "placeholder_email": placeholders,
        }

    def _create_memberships(self) -> dict[str, int]:
        created = 0
        for legacy_ref, user_id in self.user_ids.items():
            membership = Membership.objects.filter(user_id=user_id).first()
            if membership is None:
                membership = Membership.objects.create(
                    organization_id=self.organization_id,
                    user_id=user_id,
                    status=Membership.Status.ACTIVE,
                    joined_at=timezone.now(),
                )
                created += 1
            self.membership_ids[legacy_ref] = membership.id
        return {"created": created, "existing": len(self.membership_ids) - created}

    # -- M3: backfill ----------------------------------------------------------------------
    def _links(self) -> list[LinkSpec]:
        return [
            LinkSpec(
                "course_owner_department",
                Course,
                "owner_department_ref",
                "owner_department",
                "department",
            ),
            LinkSpec("course_created_by", Course, "created_by_ref", "created_by", "membership"),
            LinkSpec(
                "version_created_by", CourseVersion, "created_by_ref", "created_by", "membership"
            ),
            LinkSpec(
                "version_published_by",
                CourseVersion,
                "published_by_ref",
                "published_by",
                "membership",
            ),
            LinkSpec("media_created_by", MediaAsset, "created_by_ref", "created_by", "membership"),
            LinkSpec(
                "assignment_target_membership",
                Assignment,
                "target_ref",
                "target_membership",
                "membership",
                filters={"target_type": Assignment.TargetType.USER},
            ),
            LinkSpec(
                "assignment_target_department",
                Assignment,
                "target_ref",
                "target_department",
                "department",
                filters={"target_type": Assignment.TargetType.DEPARTMENT},
            ),
            LinkSpec(
                "assignment_assigned_by", Assignment, "assigned_by_ref", "assigned_by", "membership"
            ),
            LinkSpec(
                "enrollment_membership",
                Enrollment,
                "user_ref",
                "membership",
                "membership",
                required=True,
            ),
            LinkSpec(
                "completion_membership",
                CompletionRecord,
                "user_ref",
                "membership",
                "membership",
                required=True,
            ),
            LinkSpec(
                "completion_user", CompletionRecord, "user_ref", "user_id", "user", required=True
            ),
            LinkSpec(
                "reminder_recipient_membership",
                ReminderLog,
                "recipient_ref",
                "recipient_membership",
                "membership",
                required=True,
            ),
            LinkSpec(
                "notification_recipient_user",
                NotificationLog,
                "recipient_ref",
                "recipient_user",
                "user",
                required=True,
            ),
            LinkSpec(
                "notification_recipient_membership",
                NotificationLog,
                "recipient_ref",
                "recipient_membership",
                "membership",
                required=True,
            ),
            LinkSpec(
                "grant_membership",
                PermissionGrant,
                "user_ref",
                "membership",
                "membership",
                required=True,
            ),
            LinkSpec(
                "grant_scope_department",
                PermissionGrant,
                "scope_ref",
                "scope_department",
                "department",
                filters={"scope_type": PermissionGrant.Scope.DEPARTMENT},
            ),
            LinkSpec(
                "grant_granted_by", PermissionGrant, "granted_by_ref", "granted_by", "membership"
            ),
            LinkSpec(
                "suspension_membership",
                AccessSuspension,
                "user_ref",
                "membership",
                "membership",
                required=True,
            ),
            LinkSpec(
                "suspension_suspended_by",
                AccessSuspension,
                "suspended_by_ref",
                "suspended_by",
                "membership",
            ),
            LinkSpec(
                "suspension_lifted_by", AccessSuspension, "lifted_by_ref", "lifted_by", "membership"
            ),
            LinkSpec(
                "audit_actor_user",
                AuditEvent,
                "actor_ref",
                "actor_user_id",
                "user",
                allow_system=True,
            ),
            LinkSpec(
                "audit_actor_membership",
                AuditEvent,
                "actor_ref",
                "actor_membership_id",
                "membership",
                allow_system=True,
            ),
        ]

    def _mapping(self, kind: str) -> Mapping[str, UUID]:
        if kind == "department":
            return self.department_ids
        if kind == "membership":
            return self.membership_ids
        return self.user_ids

    def _planned(self, kind: str) -> set[str]:
        return self.planned_departments if kind == "department" else self.planned_users

    def _apply_link(self, link: LinkSpec) -> dict[str, Any]:
        manager = cast("QuerySet[Any]", link.model._default_manager).filter(
            organization_id=self.organization_id,
            **{f"{link.target}__isnull": True},
            **dict(link.filters),
        )
        rows = manager.count()
        mapping = self._mapping(link.mapping)
        grouped: dict[UUID, list[UUID]] = defaultdict(list)
        unresolved_refs: set[str] = set()
        unresolved = 0
        blank = 0
        system = 0
        resolvable = 0
        for pk, raw in manager.values_list("pk", link.source).iterator(chunk_size=self.batch_size):
            if raw is None:
                continue
            ref = _clean(raw)
            if not ref:
                blank += 1
                if link.required:
                    unresolved += 1
                continue
            if link.allow_system and _is_system(ref):
                system += 1
                continue
            target = mapping.get(ref)
            if target is None and (ref in self._planned(link.mapping)):
                resolvable += 1
                continue
            if target is None:
                unresolved += 1
                unresolved_refs.add(ref)
                continue
            resolvable += 1
            if not self.dry_run:
                grouped[target].append(pk)

        filled = resolvable if self.dry_run else 0
        if not self.dry_run:
            for target, ids in grouped.items():
                for batch in _chunks(ids, self.batch_size):
                    with transaction.atomic():
                        filled += link.model._default_manager.filter(pk__in=batch).update(
                            **{link.target: target}
                        )
        if link.required:
            self.unresolved_required_rows += unresolved
        return {
            "rows": rows,
            "filled": filled,
            "unresolved": unresolved,
            "unresolved_refs": sorted(unresolved_refs)[:20],
            "blank": blank,
            "system": system,
        }

    # -- reporting -------------------------------------------------------------------------
    def _reconcile(self) -> None:
        duplicate_memberships = (
            Membership.objects.values("user_id")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .count()
        )
        companies_per_account = (
            Membership.objects.values("user_id")
            .annotate(companies=Count("organization_id", distinct=True))
            .filter(companies__gt=1)
            .count()
        )
        self.report["invariants"] = {
            "users_with_more_than_one_membership": duplicate_memberships,
            "accounts_with_memberships_in_two_companies": companies_per_account,
            "required_unresolved_rows": self.unresolved_required_rows,
        }
        self.report["ok"] = (
            not self.errors
            and duplicate_memberships == 0
            and companies_per_account == 0
            and self.unresolved_required_rows == 0
        )

    def run(self) -> dict[str, Any]:
        self.report = {
            "task": "T-026 CP2",
            "organization_id": str(self.organization_id),
            "dry_run": self.dry_run,
            "batch_size": self.batch_size,
            "identities": {
                "rows": len(self.identities),
                "with_email": sum(1 for identity in self.identities if identity.email),
                "without_email": sum(1 for identity in self.identities if not identity.email),
            },
            "departments": {},
            "accounts": {},
            "memberships": {},
            "links": {},
            "deferred": {},
            "invariants": {},
            "errors": [],
        }
        self._check_company()
        if self.errors:
            self.report["errors"] = self.errors
            self.report["ok"] = False
            return self.report

        self._load_existing()
        self._validate()
        if self.errors:
            self.report["errors"] = self.errors
            self.report["ok"] = False
            return self.report

        if self.dry_run:
            self.report["departments"] = {
                "distinct_refs": len(self.department_ids) + len(self.planned_departments),
                "created": 0,
                "planned": len(self.planned_departments),
            }
            self.report["accounts"] = {
                "identities": len(self.identities),
                "created": 0,
                "planned": len(self.planned_users),
                "placeholder_email": sum(1 for item in self.identities if not item.email),
            }
            self.report["memberships"] = {"created": 0, "planned": len(self.planned_users)}
            for link in self._links():
                self.report["links"][link.name] = self._apply_link(link)
        else:
            departments = self._create_departments()
            accounts = self._create_accounts()
            memberships = self._create_memberships()
            self.report["departments"] = {
                "distinct_refs": len(self.department_ids),
                **departments,
            }
            self.report["accounts"] = {
                "identities": len(self.identities),
                **accounts,
            }
            self.report["memberships"] = memberships
            for link in self._links():
                self.report["links"][link.name] = self._apply_link(link)

        # Explicitly deferred, never silently dropped: role targets need the role model (T-028)
        # and legacy capability names are mapped in T-028 CP3.
        self.report["deferred"] = {
            "assignment_role_targets": Assignment.objects.filter(
                organization_id=self.organization_id,
                target_type=Assignment.TargetType.ROLE,
            ).count(),
            "legacy_capability_grants": PermissionGrant.objects.filter(
                organization_id=self.organization_id
            ).count(),
        }
        self._reconcile()
        self.report["errors"] = self.errors
        return self.report


def write_report(report: Mapping[str, Any], path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def backfill_tenancy(
    *,
    organization_id: UUID,
    identities: Sequence[Identity],
    dry_run: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    """Run one mapping/backfill pass and return its report."""
    if batch_size < 1:
        raise CommandError("--batch-size must be a positive integer")
    return TenancyBackfill(
        organization_id=organization_id,
        identities=identities,
        dry_run=dry_run,
        batch_size=batch_size,
    ).run()


class Command(BaseCommand):
    help = "Map legacy refs to tenancy rows and backfill the new foreign keys (T-026 CP2)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--identities",
            required=True,
            help="CSV with the header legacy_user_ref,email,display_name (owner-provided)",
        )
        parser.add_argument(
            "--organization-id",
            default=None,
            help="Company UUID (defaults to ACADEMY_ORGANIZATION_ID)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and report, write nothing",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Rows per transaction (default {DEFAULT_BATCH_SIZE})",
        )
        parser.add_argument("--report", default=None, help="Write the JSON report to this path")

    def handle(self, *args: Any, **options: Any) -> None:
        organization_id = UUID(str(options["organization_id"] or settings.ACADEMY_ORGANIZATION_ID))
        identities, errors = read_identities(str(options["identities"]))
        if errors:
            report: dict[str, Any] = {
                "task": "T-026 CP2",
                "ok": False,
                "errors": errors,
            }
            if options["report"]:
                write_report(report, str(options["report"]))
            raise CommandError("; ".join(errors[:3]))

        report = backfill_tenancy(
            organization_id=organization_id,
            identities=identities,
            dry_run=bool(options["dry_run"]),
            batch_size=int(options["batch_size"]),
        )
        if options["report"]:
            write_report(report, str(options["report"]))

        mode = "dry run" if report["dry_run"] else "backfill"
        self.stdout.write(
            f"T-026 CP2 {mode}: ok={report['ok']} "
            f"accounts={report['accounts']} memberships={report['memberships']} "
            f"departments={report['departments']} invariants={report['invariants']}"
        )
        if report["errors"]:
            for error in report["errors"]:
                self.stderr.write(error)
        if not report["ok"]:
            raise CommandError(
                "tenancy backfill did not reconcile; fix the report and re-run "
                "(the command is idempotent)"
            )
