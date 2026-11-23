"""T-002 acceptance: settings profiles, Celery queues, JSON logging and i18n.

The queue names and the task catalogue are owned by ``docs/background-jobs.md`` §1 and
``docs/operations/environments.md`` §4; these tests fail if the code stops matching them.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import pytest
import redis
from celery.app.base import Celery
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory
from django.utils import translation

from config.celery import app, ping
from config.logging import REQUEST_ID, JsonFormatter
from config.middleware import RequestIdMiddleware

MEDIA_QUEUE = "media"
NOTIFICATIONS_QUEUE = "notifications"
DEFAULT_QUEUE = "default"


def routed_queue(task_name: str) -> str:
    """Return the queue Celery would route ``task_name`` to."""
    routed: Any = app.amqp.router.route({}, task_name)
    route = routed[0] if isinstance(routed, tuple) else routed
    queue = route["queue"]
    return str(getattr(queue, "name", queue))


def broker_url_with_db(url: str, db: str) -> str:
    """The same broker with another Redis database."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{db}", parts.query, parts.fragment))


class TestCeleryQueues:
    @pytest.mark.parametrize(
        ("task_name", "expected_queue"),
        [
            ("academy.ping", DEFAULT_QUEUE),
            ("academy.media.process", MEDIA_QUEUE),
            ("academy.media.purge_abandoned", MEDIA_QUEUE),
            ("academy.notifications.send", NOTIFICATIONS_QUEUE),
            ("academy.escalations.digest", NOTIFICATIONS_QUEUE),
            ("academy.progress.compact", DEFAULT_QUEUE),
            ("academy.reminders.evaluate", DEFAULT_QUEUE),
            ("academy.audit.mirror", DEFAULT_QUEUE),
        ],
    )
    def test_documented_tasks_are_routed_to_their_queue(
        self, task_name: str, expected_queue: str
    ) -> None:
        assert routed_queue(task_name) == expected_queue

    def test_undeclared_task_falls_back_to_the_default_queue(self) -> None:
        assert routed_queue("academy.something.not.written.yet") == DEFAULT_QUEUE

    def test_only_the_documented_queues_exist(self) -> None:
        assert [queue.name for queue in settings.CELERY_TASK_QUEUES] == [
            DEFAULT_QUEUE,
            MEDIA_QUEUE,
            NOTIFICATIONS_QUEUE,
        ]
        # A misnamed task must land on `default`, never on an auto-created queue nobody reads.
        assert settings.CELERY_TASK_CREATE_MISSING_QUEUES is False


class TestWorkerPingOverRedis:
    def test_ping_returns_pong(self) -> None:
        assert ping.apply().get() == "pong"

    def test_a_ping_message_lands_on_the_default_queue(self) -> None:
        """Publish through a real Redis broker, on a database no worker consumes.

        The development worker would otherwise take the message before it could be read, so
        the probe keeps this project's routes and broker but uses a spare database.
        """
        probe_url = broker_url_with_db(str(settings.CELERY_BROKER_URL), "9")
        broker = redis.Redis.from_url(probe_url, decode_responses=True)
        broker.ping()

        probe = Celery("academy-probe", broker=probe_url)
        probe.conf.update(
            task_routes=settings.CELERY_TASK_ROUTES,
            task_default_queue=settings.CELERY_TASK_DEFAULT_QUEUE,
            task_create_missing_queues=False,
            task_always_eager=False,
        )
        try:
            broker.delete(DEFAULT_QUEUE)
            probe.send_task("academy.ping")
            assert broker.llen(DEFAULT_QUEUE) == 1
            message = broker.lindex(DEFAULT_QUEUE, 0) or ""
        finally:
            broker.delete(DEFAULT_QUEUE)

        assert "academy.ping" in message


def make_record(level: int = logging.INFO, msg: str = "hello") -> logging.LogRecord:
    return logging.LogRecord(
        name="config.example",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


class TestJsonLogging:
    def test_a_log_line_is_one_json_object(self) -> None:
        line = JsonFormatter().format(make_record())
        payload: dict[str, Any] = json.loads(line)

        assert set(payload) == {"ts", "level", "logger", "service", "env", "message"}
        assert payload["level"] == "INFO"
        assert payload["logger"] == "config.example"
        assert payload["message"] == "hello"
        assert payload["ts"].endswith("+00:00")

    def test_request_id_is_attached_when_a_request_is_in_flight(self) -> None:
        token = REQUEST_ID.set("abc-123")
        try:
            line = JsonFormatter().format(make_record())
        finally:
            REQUEST_ID.reset(token)

        payload: dict[str, Any] = json.loads(line)
        assert payload["request_id"] == "abc-123"

    def test_configured_formatter_is_the_json_one(self) -> None:
        logging_settings: Any = settings.LOGGING
        assert logging_settings["formatters"]["json"]["()"] == "config.logging.JsonFormatter"


class TestRequestId:
    @pytest.mark.django_db
    def test_safe_inbound_id_is_echoed(self) -> None:
        response = Client().get("/healthz", headers={"X-Request-ID": "support-42"})

        assert response["X-Request-ID"] == "support-42"

    def test_unsafe_inbound_id_is_replaced(self) -> None:
        seen: dict[str, str] = {}

        def responder(request: HttpRequest) -> HttpResponse:
            seen["request_id"] = REQUEST_ID.get()
            return HttpResponse("ok")

        request = RequestFactory().get("/", headers={"X-Request-ID": "bad id!"})
        response = RequestIdMiddleware(responder)(request)

        assert response["X-Request-ID"] != "bad id!"
        assert len(response["X-Request-ID"]) == 32
        assert seen["request_id"] == response["X-Request-ID"]


class TestI18n:
    def test_arabic_is_the_default_language(self) -> None:
        assert settings.LANGUAGE_CODE == "ar"
        assert settings.USE_I18N is True

    def test_english_is_available(self) -> None:
        assert dict(settings.LANGUAGES)["en"] == "English"

    def test_locale_middleware_is_installed_after_sessions(self) -> None:
        middleware = list(settings.MIDDLEWARE)

        assert middleware.index("config.middleware.RequestIdMiddleware") == 0
        assert middleware.index("django.middleware.locale.LocaleMiddleware") > middleware.index(
            "django.contrib.sessions.middleware.SessionMiddleware"
        )

    @pytest.mark.django_db
    def test_cookie_selects_english(self) -> None:
        client = Client()
        client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        try:
            client.get("/healthz")
            assert translation.get_language() == "en"
        finally:
            translation.deactivate()


def clean_env(**overrides: str) -> dict[str, str]:
    """The process environment without any ACADEMY_* value, plus the given overrides."""
    env = {name: value for name, value in os.environ.items() if not name.startswith("ACADEMY_")}
    env.update(overrides)
    return env


def import_profile(profile: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", f"import config.settings.{profile}"],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(settings.BASE_DIR),
        check=False,
    )


class TestProfiles:
    def test_production_refuses_to_start_without_allowed_hosts(self) -> None:
        result = import_profile(
            "prod",
            clean_env(DJANGO_SETTINGS_MODULE="config.settings.prod", DJANGO_SECRET_KEY="k" * 60),
        )

        assert result.returncode != 0
        assert "ACADEMY_ALLOWED_HOSTS" in result.stderr

    def test_production_refuses_a_short_secret_key(self) -> None:
        result = import_profile(
            "prod",
            clean_env(
                DJANGO_SETTINGS_MODULE="config.settings.prod",
                DJANGO_SECRET_KEY="short",
                ACADEMY_ALLOWED_HOSTS="academy.example.com",
                ACADEMY_CSRF_TRUSTED_ORIGINS="https://hub.example.com",
            ),
        )

        assert result.returncode != 0
        assert "DJANGO_SECRET_KEY" in result.stderr

    def test_production_loads_with_the_required_values(self) -> None:
        result = import_profile(
            "prod",
            clean_env(
                DJANGO_SETTINGS_MODULE="config.settings.prod",
                DJANGO_SECRET_KEY="k" * 60,
                ACADEMY_ALLOWED_HOSTS="academy.example.com",
                ACADEMY_CSRF_TRUSTED_ORIGINS="https://hub.example.com",
                ACADEMY_DB_PASSWORD="ci",
            ),
        )

        assert result.returncode == 0, result.stderr
