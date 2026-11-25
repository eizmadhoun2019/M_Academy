"""Shared settings.

Every value here has a row in ``docs/configuration.md``. If a variable is not documented
there, it does not belong in this file.
"""

from __future__ import annotations

import json
import mimetypes
import os
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured
from kombu import Queue

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def env_json(name: str, default: str = "{}") -> dict[str, str]:
    """A JSON object from the environment; an empty value is an empty mapping."""
    raw = os.environ.get(name, "").strip() or default
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ImproperlyConfigured(f"{name} must be a JSON object ({error})") from error
    if not isinstance(value, dict):
        raise ImproperlyConfigured(f"{name} must be a JSON object")
    return {str(key): str(secret) for key, secret in value.items()}


# --- Identity and core -------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env_bool("ACADEMY_DEBUG", False)
ALLOWED_HOSTS = env_list("ACADEMY_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("ACADEMY_CSRF_TRUSTED_ORIGINS")
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
APPEND_SLASH = False

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "academy",
]

MIDDLEWARE = [
    # First, so every log line and response below carries the request id.
    "config.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # After sessions and before common: Django's required order for locale selection.
    "django.middleware.locale.LocaleMiddleware",
    # In hub mode the proxy's signed assertion supplies the identity (T-015).
    "academy.hub.identity.HubIdentityMiddleware",
    # Resolves the caller once for the API and the pages (T-014); needs the session above.
    "academy.access.middleware.AcademyAccessMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Media upload policy (docs/configuration.md §3) ---------------------------
ACADEMY_UPLOAD_MAX_VIDEO_BYTES = env_int("ACADEMY_UPLOAD_MAX_VIDEO_BYTES", 2147483648)
ACADEMY_UPLOAD_MAX_IMAGE_BYTES = env_int("ACADEMY_UPLOAD_MAX_IMAGE_BYTES", 10485760)
ACADEMY_UPLOAD_MAX_DOCUMENT_BYTES = env_int("ACADEMY_UPLOAD_MAX_DOCUMENT_BYTES", 26214400)
ACADEMY_UPLOAD_VIDEO_TYPES = env_list("ACADEMY_UPLOAD_VIDEO_TYPES", "video/mp4")
ACADEMY_UPLOAD_IMAGE_TYPES = env_list(
    "ACADEMY_UPLOAD_IMAGE_TYPES", "image/png,image/jpeg,image/webp"
)
ACADEMY_UPLOAD_DOCUMENT_TYPES = env_list("ACADEMY_UPLOAD_DOCUMENT_TYPES", "application/pdf")
ACADEMY_UPLOAD_MAX_DURATION_SECONDS = env_int("ACADEMY_UPLOAD_MAX_DURATION_SECONDS", 14400)
ACADEMY_UPLOAD_URL_TTL_SECONDS = env_int("ACADEMY_UPLOAD_URL_TTL_SECONDS", 900)
ACADEMY_UPLOAD_ABANDON_HOURS = env_int("ACADEMY_UPLOAD_ABANDON_HOURS", 24)
ACADEMY_PLAYBACK_URL_TTL_SECONDS = env_int("ACADEMY_PLAYBACK_URL_TTL_SECONDS", 300)

# --- Video pipeline (docs/configuration.md §4) -------------------------------
ACADEMY_HLS_RENDITIONS = env_list("ACADEMY_HLS_RENDITIONS", "360p,720p")
ACADEMY_HLS_360P = env("ACADEMY_HLS_360P", "640x360,800k,96k")
ACADEMY_HLS_720P = env("ACADEMY_HLS_720P", "1280x720,2500k,128k")
ACADEMY_HLS_SEGMENT_SECONDS = env_int("ACADEMY_HLS_SEGMENT_SECONDS", 6)
ACADEMY_HLS_GOP_FRAMES = env_int("ACADEMY_HLS_GOP_FRAMES", 48)
ACADEMY_HLS_SEGMENT_TYPE = env("ACADEMY_HLS_SEGMENT_TYPE", "mpegts")
ACADEMY_TRANSCODE_TIMEOUT_SECONDS = env_int("ACADEMY_TRANSCODE_TIMEOUT_SECONDS", 3600)
ACADEMY_TRANSCODE_ATTEMPTS = env_int("ACADEMY_TRANSCODE_ATTEMPTS", 2)
ACADEMY_KEEP_ORIGINALS = env_bool("ACADEMY_KEEP_ORIGINALS", False)

# --- Reports (docs/reports.md §4) --------------------------------------------
# Cursor paging is opt-in on the report lists; a page without ``cursor=`` keeps the page
# numbers, and this is the page size ``cursor=`` returns.
ACADEMY_CURSOR_PAGE_SIZE = env_int("ACADEMY_CURSOR_PAGE_SIZE", 50)

# --- Adapters (ARCHITECTURE.md §4) -------------------------------------------
# Four host seams, each named by a ``module.path:ClassName`` value and resolved on first use
# by ``academy.adapters.loader``. Empty means "not configured": the loader raises instead of
# substituting a default (docs/configuration.md §11).
ACADEMY_ADAPTERS = {
    "identity": env("ACADEMY_ADAPTER_IDENTITY"),
    "organization": env("ACADEMY_ADAPTER_ORGANIZATION"),
    "notify": env("ACADEMY_ADAPTER_NOTIFY"),
    "storage": env("ACADEMY_ADAPTER_STORAGE"),
}

# --- Data stores -------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": env("ACADEMY_DB_HOST", "db"),
        "PORT": env("ACADEMY_DB_PORT", "5432"),
        "NAME": env("ACADEMY_DB_NAME", "academy"),
        "USER": env("ACADEMY_DB_USER", "academy"),
        "PASSWORD": env("ACADEMY_DB_PASSWORD"),
        "CONN_MAX_AGE": env_int("ACADEMY_DB_CONN_MAX_AGE", 60),
        "CONN_HEALTH_CHECKS": True,
    }
}

REDIS_URL = env("ACADEMY_REDIS_URL", "redis://redis:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "macademy",
        "TIMEOUT": env_int("ACADEMY_CACHE_TTL_SECONDS", 60),
    }
}

# --- Branding and business time (docs/configuration.md §1) ------------------
# Reminder anchors are calendar days in the organization's zone (D-002 keeps UTC as the default,
# so storage, logs and reminders agree in the standard deployment).
try:
    ACADEMY_BUSINESS_TZ = str(ZoneInfo(env("ACADEMY_BUSINESS_TZ", "UTC")))
except ZoneInfoNotFoundError as error:
    raise ImproperlyConfigured(f"ACADEMY_BUSINESS_TZ is not a known zone ({error})") from error
# The organization display name the notification copy substitutes for `{org}` and prints in the
# brand line of every message (docs/notifications.md §3).
ACADEMY_ORGANIZATION_NAME = env("ACADEMY_ORGANIZATION_NAME", "مشيد")

# --- Celery ----------------------------------------------------------------
# Queues are fixed by docs/operations/environments.md §4 and the catalogue that fills them is
# docs/background-jobs.md §1. A task name that matches no route lands on `default` instead of
# silently creating a queue no worker consumes.
CELERY_BROKER_URL = env("ACADEMY_CELERY_BROKER_URL", "redis://redis:6379/1")
CELERY_RESULT_BACKEND = env("ACADEMY_CELERY_RESULT_URL", "redis://redis:6379/2")
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_RESULT_EXPIRES = 86400
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_CREATE_MISSING_QUEUES = False
CELERY_TASK_QUEUES = (Queue("default"), Queue("media"), Queue("notifications"))
CELERY_TASK_ROUTES = {
    "academy.media.*": {"queue": "media"},
    "academy.notifications.*": {"queue": "notifications"},
    "academy.escalations.*": {"queue": "notifications"},
    "academy.*": {"queue": "default"},
}


# The beat schedule (docs/background-jobs.md §4) is declared with the tasks it names: T-018 for
# media and T-021 for reminders. Scheduling a task that does not exist would only fill the
# queues with messages no worker can route.
#
# Celery beats in UTC (CELERY_TIMEZONE above), while the reminder table is anchored in business
# time, so the one business-time entry converts its hour once when the process starts. With the
# default `ACADEMY_BUSINESS_TZ=UTC` (D-002) the conversion is the identity; a zone with DST
# drifts by an hour until the next deploy, which is why the default is UTC.
def _business_crontab(hour: int, minute: int = 0) -> crontab:
    local = datetime.now(ZoneInfo(ACADEMY_BUSINESS_TZ))
    target = local.replace(hour=hour, minute=minute, second=0, microsecond=0).astimezone(UTC)
    return crontab(hour=target.hour, minute=target.minute)


_DAILY_08 = _business_crontab(8)
CELERY_BEAT_SCHEDULE = {
    "notifications-sweep": {
        "task": "academy.notifications.sweep",
        "schedule": crontab(minute="*/15"),
    },
    "reminders-evaluate": {"task": "academy.reminders.evaluate", "schedule": _DAILY_08},
    "escalations-digest": {"task": "academy.escalations.digest", "schedule": _DAILY_08},
}

# --- Email (Hub mail API arrives with T-015) ---------------------------------
EMAIL_BACKEND = env("ACADEMY_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("ACADEMY_EMAIL_HOST", "mailhog")
EMAIL_PORT = env_int("ACADEMY_EMAIL_PORT", 1025)
EMAIL_USE_TLS = env_bool("ACADEMY_EMAIL_USE_TLS", False)

# --- Sessions, cookies, CSRF (namespaced; see environments.md §5) ------------
SESSION_COOKIE_NAME = env("ACADEMY_SESSION_COOKIE_NAME", "m_academy_sessionid")
SESSION_COOKIE_AGE = env_int("ACADEMY_SESSION_COOKIE_AGE", 28800)

# D-027: the compatibility union is the default; H1 production sets `grants_only`.
ACADEMY_AUTHORIZATION_MODE = env("ACADEMY_AUTHORIZATION_MODE", "role_plus_grants")

# D-026: `hub` trusts only a verified Hub identity; `standalone` uses a local sign-in.
ACADEMY_ACCESS_MODE = env("ACADEMY_ACCESS_MODE", "hub")
if ACADEMY_ACCESS_MODE not in ("hub", "standalone"):
    raise ImproperlyConfigured(
        f"ACADEMY_ACCESS_MODE must be 'hub' or 'standalone', got {ACADEMY_ACCESS_MODE!r}"
    )
# One deployment serves one organization (D-026); the Hub assertion must name this UUID.
ACADEMY_ORGANIZATION_ID = env("ACADEMY_ORGANIZATION_ID", "25498ed9-13b1-4f10-8294-859ff80a41b7")
DEVELOPMENT_LOGIN = env_bool("ACADEMY_DEVELOPMENT_LOGIN", False)
THROTTLES_ENABLED = env_bool("ACADEMY_THROTTLES_ENABLED", True)
THROTTLE_RATES = {
    "anon": "20/min",
    "login": "10/min",
    "heartbeat": "30/min",
    "playback": "30/min",
    "read": "120/min",
    "write": "60/min",
    "export": "5/hour",
    "webhook": "600/min",
}

# --- Hub integration (docs/hub-contract.md §5) -------------------------------
ACADEMY_HUB_ORIGIN = env("ACADEMY_HUB_ORIGIN")
ACADEMY_HUB_UPSTREAM_HOST = env("ACADEMY_HUB_UPSTREAM_HOST")
ACADEMY_TRUSTED_PROXY_NETWORKS = env_list("ACADEMY_TRUSTED_PROXY_NETWORKS")
ACADEMY_PROXY_PATH_PREFIX = env("ACADEMY_PROXY_PATH_PREFIX", "/academy")
ACADEMY_STORAGE_CORS_ORIGIN = env("ACADEMY_STORAGE_CORS_ORIGIN")
ACADEMY_HUB_API_BASE_URL = env("ACADEMY_HUB_API_BASE_URL")
ACADEMY_HUB_API_TOKEN = env("ACADEMY_HUB_API_TOKEN")
try:
    ACADEMY_HUB_API_PATHS: dict[str, str] = json.loads(env("ACADEMY_HUB_API_PATHS", "{}") or "{}")
except json.JSONDecodeError as error:
    raise ImproperlyConfigured(f"ACADEMY_HUB_API_PATHS must be a JSON object ({error})") from error
ACADEMY_HUB_IDENTITY_KEYS = env_json("ACADEMY_HUB_IDENTITY_KEYS")
ACADEMY_HUB_WEBHOOK_KEYS = env_json("ACADEMY_HUB_WEBHOOK_KEYS")
ACADEMY_HUB_IDENTITY_VERIFIER = env("ACADEMY_HUB_IDENTITY_VERIFIER")
ACADEMY_HUB_IDENTITY_HEADER = env("ACADEMY_HUB_IDENTITY_HEADER", "X-Masheed-Identity")
ACADEMY_HUB_WEBHOOK_HEADER = env("ACADEMY_HUB_WEBHOOK_HEADER", "X-Masheed-Webhook")
ACADEMY_HUB_WEBHOOK_PATH = env("ACADEMY_HUB_WEBHOOK_PATH", "/internal/hub/webhooks/")
ACADEMY_HUB_ISSUER = env("ACADEMY_HUB_ISSUER", "masheed-hub")
ACADEMY_HUB_AUDIENCE = env("ACADEMY_HUB_AUDIENCE", "masheed-academy")
ACADEMY_HUB_ASSERTION_TTL = env_int("ACADEMY_HUB_ASSERTION_TTL", 60)
ACADEMY_HUB_WEBHOOK_TTL = env_int("ACADEMY_HUB_WEBHOOK_TTL", 300)
ACADEMY_HUB_CLOCK_SKEW = env_int("ACADEMY_HUB_CLOCK_SKEW", 5)
ACADEMY_HUB_CONNECT_TIMEOUT = float(env("ACADEMY_HUB_CONNECT_TIMEOUT", "0.5"))
ACADEMY_HUB_READ_TIMEOUT = float(env("ACADEMY_HUB_READ_TIMEOUT", "1"))
ACADEMY_HUB_API_RETRIES = env_int("ACADEMY_HUB_API_RETRIES", 1)
ACADEMY_HUB_RETRY_BACKOFF = float(env("ACADEMY_HUB_RETRY_BACKOFF", "0.1"))
ACADEMY_HUB_CIRCUIT_FAILURES = env_int("ACADEMY_HUB_CIRCUIT_FAILURES", 3)
ACADEMY_HUB_CIRCUIT_SECONDS = env_int("ACADEMY_HUB_CIRCUIT_SECONDS", 30)
ACADEMY_HUB_DIRECTORY_TTL = env_int("ACADEMY_HUB_DIRECTORY_TTL", 60)
ACADEMY_HUB_NAVIGATION_SOURCE = env("ACADEMY_HUB_NAVIGATION_SOURCE", "settings")
try:
    ACADEMY_HUB_NAVIGATION: list[dict[str, str]] = json.loads(
        env("ACADEMY_HUB_NAVIGATION", "[]") or "[]"
    )
except json.JSONDecodeError as error:
    raise ImproperlyConfigured(f"ACADEMY_HUB_NAVIGATION must be a JSON array ({error})") from error
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_NAME = "academy_csrftoken"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

# --- i18n, time, static ------------------------------------------------------
LANGUAGES = [("ar", "العربية"), ("en", "English")]
LANGUAGE_CODE = env("ACADEMY_DEFAULT_LANGUAGE", "ar")
if LANGUAGE_CODE not in dict(LANGUAGES):
    raise ImproperlyConfigured(
        f"ACADEMY_DEFAULT_LANGUAGE must be one of {sorted(dict(LANGUAGES))}, got {LANGUAGE_CODE!r}"
    )
USE_I18N = True
# The cookie LocaleMiddleware reads; namespaced like the session cookie would be a change of
# the documented value, so it stays Django's name (docs/configuration.md §1).
LANGUAGE_COOKIE_NAME = "django_language"
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Source styles, the locally hosted Arabic font and its licence (RULES §UI and frontend).
STATICFILES_DIRS = [BASE_DIR / "static"]
# Windows registries have no woff2 entry, so the development server would answer with
# application/octet-stream; the browser then refuses a strict font MIME check.
mimetypes.add_type("font/woff2", ".woff2")
MEDIA_ROOT = env("ACADEMY_MEDIA_ROOT", "/data/media")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Request limits and API --------------------------------------------------
DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("ACADEMY_API_BODY_LIMIT_BYTES", 2 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_VERSIONING_CLASS": None,
    # docs/api.md §1: one error envelope, page/page_size pagination and a 401 without identity.
    "EXCEPTION_HANDLER": "academy.api.errors.academy_exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": ["academy.api.authentication.AcademyAccessAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "academy.api.pagination.AcademyPagination",
    "PAGE_SIZE": 25,
    # docs/configuration.md §6; the test profile turns the counters off.
    "DEFAULT_THROTTLE_CLASSES": [
        "academy.api.throttles.AcademyAnonThrottle",
        "academy.api.throttles.AcademyUserThrottle",
    ]
    if THROTTLES_ENABLED
    else [],
    "DEFAULT_THROTTLE_RATES": THROTTLE_RATES,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Masheed Academy API",
    # One shared component for the two "organization | department" choice sets.
    "ENUM_NAME_OVERRIDES": {
        "ScopeTypeEnum": ["organization", "department"],
        "LessonContentTypeEnum": ["video", "text", "pdf"],
    },
    "DESCRIPTION": "Endpoint inventory: docs/api.md",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- Logging ----------------------------------------------------------------
# One JSON object per line on stdout; the container runtime collects it (ARCHITECTURE §3).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "config.logging.JsonFormatter"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        }
    },
    "root": {"handlers": ["console"], "level": env("ACADEMY_LOG_LEVEL", "INFO")},
}
