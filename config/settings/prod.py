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
