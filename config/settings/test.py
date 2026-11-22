"""Test profile: PostgreSQL, in-memory email, eager Celery, throttles off."""

from __future__ import annotations

import os

from .base import *  # noqa: F403
from .base import env

SECRET_KEY = "test-only-key-not-used-outside-tests-000000000000"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

DATABASES["default"]["HOST"] = env("ACADEMY_TEST_DB_HOST", env("ACADEMY_DB_HOST", "db"))  # noqa: F405
DATABASES["default"]["NAME"] = env("ACADEMY_TEST_DB_NAME", "test_academy")  # noqa: F405

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
THROTTLES_ENABLED = False
MEDIA_ROOT = os.path.join(os.path.dirname(os.environ.get("TMPDIR", "/tmp")), "academy-test-media")
