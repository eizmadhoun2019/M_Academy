"""The one guarded way to create the first ``academy.admin`` grant (``docs/api.md`` §2)."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from academy.access.principals import organization_id
from academy.grants.service import _active_admin_rows, grant


class Command(BaseCommand):
    help = "Provision the first academy.admin grant; refuses when one already exists."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--user-ref", required=True, help="Verified Hub user reference")

    def handle(self, *args: Any, **options: Any) -> None:
        org = organization_id()
        if _active_admin_rows(org):
            raise CommandError("an active academy.admin grant already exists")
        row = grant(
            organization_id=org,
            actor_ref="system:provision",
            user_ref=str(options["user_ref"]),
            capability="academy.admin",
            scope_type="organization",
        )
        self.stdout.write(self.style.SUCCESS(f"granted academy.admin to {row.user_ref}"))
