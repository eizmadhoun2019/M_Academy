"""Root URL configuration.

Operational routes, the versioned Academy API, the i18n switch and the Academy web pages.
"""

from django.conf import settings
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView
from rest_framework.permissions import AllowAny

from config.dev_static import serve as serve_dev_static
from config.health import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    # The language switch posts here (django.conf.urls.i18n) and redirects back.
    path("i18n/", include("django.conf.urls.i18n")),
    path("academy/", include("academy.ui.urls")),
    path("api/v1/academy/", include("academy.api.urls")),
    # Development/staging only; the production profile disables this route (docs/api.md §9).
    path(
        "api/schema",
        SpectacularAPIView.as_view(permission_classes=[AllowAny], authentication_classes=[]),
        name="openapi-schema",
    ),
]

if settings.DEBUG:
    # The development stack runs gunicorn, which does not serve static files the way
    # ``runserver`` does (docs/operations/environments.md). The route exists only with DEBUG.
    urlpatterns += [re_path(r"^static/(?P<path>.*)$", serve_dev_static)]

handler403 = "academy.ui.errors.forbidden"
handler404 = "academy.ui.errors.not_found"
handler500 = "academy.ui.errors.server_error"
