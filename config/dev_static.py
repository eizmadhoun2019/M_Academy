"""Development-only static file serving.

gunicorn does not serve static files, so the development profile mounts this view. It adds
``no-store`` because the browser otherwise caches a stylesheet heuristically from its
Last-Modified header and shows yesterday's CSS after an edit.
"""

from __future__ import annotations

from django.contrib.staticfiles.views import serve as serve_static
from django.http import HttpRequest, HttpResponseBase


def serve(request: HttpRequest, path: str) -> HttpResponseBase:
    response = serve_static(request, path)
    response["Cache-Control"] = "no-store"
    return response
