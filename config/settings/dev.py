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
