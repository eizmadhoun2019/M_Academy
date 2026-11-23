"""JSON log records for every Academy process.

One line is one JSON object, so a collector indexes it without a regular expression. The
request id set by ``config.middleware.RequestIdMiddleware`` is attached when a line belongs to
a request. ``docs/configuration.md`` §1 forbids personal data here: no tokens, cookies, emails
or media URLs ever reach a log line.
"""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from datetime import UTC, datetime

REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="")

SERVICE_NAME = "academy"


class JsonFormatter(logging.Formatter):
    """Render a log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "service": SERVICE_NAME,
            "env": os.environ.get("ACADEMY_ENV", "development"),
            "message": record.getMessage(),
        }

        request_id = REQUEST_ID.get()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        # ensure_ascii=False keeps Arabic readable for the owner reading raw container output.
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
