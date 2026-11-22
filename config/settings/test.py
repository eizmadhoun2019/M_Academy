"""Test profile: PostgreSQL, in-memory email, eager Celery, throttles off."""

from __future__ import annotations

import os
import tempfile

from .base import *  # noqa: F403
from .base import env

# Public test-only constant: the test profile runs no real traffic and signs nothing that
# leaves the test process, so a generated or environment-supplied key would add no safety.
SECRET_KEY = "test-only-key-not-used-outside-tests-000000000000"  # nosec B105
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

DATABASES["default"]["HOST"] = env("ACADEMY_TEST_DB_HOST", env("ACADEMY_DB_HOST", "db"))  # noqa: F405
DATABASES["default"]["NAME"] = env("ACADEMY_TEST_DB_NAME", "test_academy")  # noqa: F405

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
THROTTLES_ENABLED = False
MEDIA_ROOT = os.path.join(tempfile.gettempdir(), "academy-test-media")
