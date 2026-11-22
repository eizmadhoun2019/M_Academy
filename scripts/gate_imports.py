"""Gate G7 (part 1) — import boundary.

``academy/`` must never import ``host_stub``, ``config.settings`` internals or a Django user
model. The tenant-isolation half of G7 lives in the test suite (T-010).

The gate is inactive while the package does not exist and activates automatically once
``academy/`` is added by T-003; it is never skipped by hand.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "academy"

FORBIDDEN_PREFIXES = ("host_stub", "django.contrib.auth.models")
FORBIDDEN_NAMES = {"User", "get_user_model", "AUTH_USER_MODEL"}


def violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(FORBIDDEN_PREFIXES):
                    found.append(f"{path.name}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(FORBIDDEN_PREFIXES):
                found.append(f"{path.name}:{node.lineno}: from {module}")
            for alias in node.names:
                if alias.name in FORBIDDEN_NAMES:
                    found.append(f"{path.name}:{node.lineno}: {module}.{alias.name}")
    return found


def main() -> int:
    if not PACKAGE.is_dir():
        print("G7 import boundary: academy/ does not exist yet (T-003) — nothing to check")
        return 0

    problems: list[str] = []
    for path in PACKAGE.rglob("*.py"):
        problems.extend(f"{path.relative_to(ROOT)}: {item}" for item in violations(path))

    if problems:
        print("G7 import boundary FAILED")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("G7 import boundary passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
