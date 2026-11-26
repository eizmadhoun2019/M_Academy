"""T-026 CP2 acceptance evidence: the reconciliation audit reports counts, never content."""

from __future__ import annotations

import json
from io import StringIO

from django.core.management import call_command
from factories import make_enrollment

from academy.models import Enrollment, Organization


def _run(*args: str) -> str:
    out = StringIO()
    call_command("audit_legacy_data", *args, stdout=out)
    return out.getvalue()


def test_the_audit_reports_no_migration_target_on_an_empty_database(db: object) -> None:
    report = json.loads(_run("--json"))

    assert report["tenancy"]["Organization"] == Organization.objects.count()
    assert report["tenancy"]["User"] == 0
    assert report["tenancy"]["Membership"] == 0
    assert report["integrity"]["tenant_rows_total"] == 0
    assert report["integrity"]["rows_missing_a_link"] == 0
    assert report["distinct_refs"]["total"] == 0
    assert report["needs_migration"] is False


def test_legacy_rows_and_their_missing_links_are_counted(db: object) -> None:
    make_enrollment(Organization.objects.get(slug="masheed").pk, user_ref="u-learner")

    report = json.loads(_run("--json"))

    assert report["tables"]["Enrollment"]["rows"] == 1
    assert report["tables"]["Enrollment"]["null_links"]["membership"] == 1
    # The factory graph also names its author, so the union holds the learner and the author.
    assert report["distinct_refs"]["total"] == 2
    assert report["distinct_refs"]["per_field"]["Enrollment"] == {"user_ref": 1}
    assert report["needs_migration"] is True


def test_no_reference_value_is_printed(db: object) -> None:
    make_enrollment(Organization.objects.get(slug="masheed").pk, user_ref="u-secret-reference")

    assert "u-secret-reference" not in _run("--json")
    assert "u-secret-reference" not in _run()
    assert Enrollment.objects.filter(user_ref="u-secret-reference").exists()
