"""App configuration for the ``academy`` package."""

from __future__ import annotations

from django.apps import AppConfig


class AcademyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "academy"
    verbose_name = "Academy"

    def ready(self) -> None:
        # drf-spectacular discovers extensions only from imported modules, so the app imports
        # its schema module once at startup (docs/api.md §9).
        from academy import schema  # noqa: F401
