"""Celery application.

Task catalogue, queues and schedules are owned by ``docs/background-jobs.md``; T-002 adds the
queue routing, logging and beat schedule. T-001 only proves a worker can start on this
project's own broker.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("academy")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(name="academy.ping")
def ping() -> str:
    """Trivial task used by the T-002 worker smoke check."""
    return "pong"
