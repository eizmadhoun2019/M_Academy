"""Development and test implementations of the four host seams.

``academy`` never imports this package (gate G7). A deployment selects these classes through
``ACADEMY_ADAPTER_*`` the same way it selects a Hub or S3 implementation, so nothing about the
development behaviour is hard-wired into the application.
"""

from __future__ import annotations

__all__ = ["identity", "notify", "organization", "storage"]
