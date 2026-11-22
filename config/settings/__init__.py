"""Settings profiles: ``dev``, ``test``, ``prod`` (see ``docs/configuration.md``)."""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
