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

        # The notification handlers are the only subscribers the package installs itself; the
        # subscription is idempotent and tests take it down again (T-021).
        #
        # The task module is imported for its registration side effect: ``shared_task`` binds a
        # task to the app when the app finalizes, so a module imported after the first ``app.tasks``
        # access would never reach the registry. Django runs ``ready()`` before any worker or test
        # finalizes the Celery app.
        from academy.notifications import handlers, tasks  # noqa: F401

        handlers.subscribe_all()
