"""Production profile.

Startup fails loudly instead of running with an unsafe configuration
(``docs/hub-contract.md`` §7 requires the same behaviour for Hub credentials).
"""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env_list

DEBUG = False
ALLOWED_HOSTS = env_list("ACADEMY_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ACADEMY_ALLOWED_HOSTS must be set in production")

if len(SECRET_KEY) < 50:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be at least 50 characters")

if env_list("ACADEMY_CSRF_TRUSTED_ORIGINS") == []:  # noqa: F405
    raise ImproperlyConfigured("ACADEMY_CSRF_TRUSTED_ORIGINS must be set in production")

# TLS terminates at the trusted Academy ingress (docs/hub-contract.md §7).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
DEVELOPMENT_LOGIN = False

# Hub credentials are mandatory in production (docs/hub-contract.md §5).
for _name in ("ACADEMY_HUB_ORIGIN", "ACADEMY_HUB_API_BASE_URL", "ACADEMY_HUB_API_TOKEN"):
    if not globals().get(_name):  # noqa: F405
        raise ImproperlyConfigured(f"{_name} must be set in production")
for _ring in ("ACADEMY_HUB_IDENTITY_KEYS", "ACADEMY_HUB_WEBHOOK_KEYS"):
    _keys = globals().get(_ring) or {}  # noqa: F405
    if not _keys:
        raise ImproperlyConfigured(f"{_ring} must configure at least one key in production")
    if any(len(secret.encode("utf-8")) < 32 for secret in _keys.values()):
        raise ImproperlyConfigured(f"{_ring} keys must be at least 32 UTF-8 bytes")
