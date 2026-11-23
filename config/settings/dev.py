"""Development profile (local Docker stack)."""

from __future__ import annotations

from .base import *  # noqa: F403
from .base import BASE_DIR, env, env_list

DEBUG = True
ALLOWED_HOSTS = env_list("ACADEMY_ALLOWED_HOSTS", "localhost,127.0.0.1,web,testserver")
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
MEDIA_ROOT = env("ACADEMY_MEDIA_ROOT", str(BASE_DIR / "local_media"))
DEVELOPMENT_LOGIN = env("ACADEMY_DEVELOPMENT_LOGIN", "true").lower() == "true"

# The development stack runs against the stubs unless an adapter is configured explicitly, so a
# fresh clone works without a Hub or a bucket (docs/configuration.md §11).
ACADEMY_ADAPTERS = {  # noqa: F405 - name comes from `base` via the star import
    "identity": env("ACADEMY_ADAPTER_IDENTITY") or "host_stub.identity:DevelopmentIdentity",
    "organization": env("ACADEMY_ADAPTER_ORGANIZATION") or "host_stub.organization:StubDirectory",
    "notify": env("ACADEMY_ADAPTER_NOTIFY") or "host_stub.notify:RecordingNotifier",
    "storage": env("ACADEMY_ADAPTER_STORAGE") or "host_stub.storage:InMemoryStorage",
}
