"""Shared settings.

Every value here has a row in ``docs/configuration.md``. If a variable is not documented
there, it does not belong in this file.
"""

from __future__ import annotations

import os
from pathlib import Path

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

# --- Email (Hub mail API arrives with T-015) ---------------------------------
EMAIL_BACKEND = env("ACADEMY_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("ACADEMY_EMAIL_HOST", "mailhog")
EMAIL_PORT = env_int("ACADEMY_EMAIL_PORT", 1025)
EMAIL_USE_TLS = env_bool("ACADEMY_EMAIL_USE_TLS", False)

# --- Sessions, cookies, CSRF (namespaced; see environments.md §5) ------------
SESSION_COOKIE_NAME = env("ACADEMY_SESSION_COOKIE_NAME", "m_academy_sessionid")
SESSION_COOKIE_AGE = env_int("ACADEMY_SESSION_COOKIE_AGE", 28800)
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
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Masheed Academy API",
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
