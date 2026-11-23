"""App configuration for the ``academy`` package."""

from __future__ import annotations

from django.apps import AppConfig


class AcademyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "academy"
    verbose_name = "Academy"
