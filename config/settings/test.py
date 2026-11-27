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

# The test profile runs every seam against its in-memory stub, so the loader is exercised for
# real instead of being bypassed by a direct import (docs/configuration.md §8, §11).
ACADEMY_ADAPTERS = {  # noqa: F405 - name comes from `base` via the star import
    "identity": "host_stub.identity:DevelopmentIdentity",
    "organization": "host_stub.organization:StubDirectory",
    "notify": "host_stub.notify:RecordingNotifier",
    "storage": "host_stub.storage:InMemoryStorage",
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# Public test-only constant: TOTP secrets never leave the test database (T-027 CP2).
ACADEMY_MFA_ENCRYPTION_KEY = "test-only-mfa-key-not-used-outside-tests-000000"  # nosec B105
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
# Dev/test use the local sign-in and start from the H1 authorization mode (D-027).
ACADEMY_ACCESS_MODE = "standalone"
DEVELOPMENT_LOGIN = True
THROTTLES_ENABLED = False
MEDIA_ROOT = os.path.join(tempfile.gettempdir(), "academy-test-media")
