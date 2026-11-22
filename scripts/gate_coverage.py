"""Gate G3 (part 2) — coverage ≥ 85% on ``academy/services`` and ``academy/selectors``.

Run after ``pytest --cov --cov-report=json``. The threshold applies to the business-logic
packages only (RULES → CI gates). While those packages do not exist (before T-003) the gate
reports that it is inactive instead of measuring an empty set as 0%.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

THRESHOLD = 85.0
TARGET_PARTS = ("services", "selectors")


def main() -> int:
    report = Path("coverage.json")
    if not report.is_file():
        print("G3 coverage: coverage.json missing — run pytest with --cov-report=json")
        return 1

    data = json.loads(report.read_text(encoding="utf-8"))
    files = data.get("files", {})

    total_statements = 0
    total_missing = 0
    measured = 0
    for name, info in files.items():
        parts = Path(name).parts
        if not any(part in TARGET_PARTS for part in parts):
            continue
        if "migrations" in parts:
            continue
        measured += 1
        summary = info["summary"]
        total_statements += summary["num_statements"]
        total_missing += summary["missing_lines"]

    if measured == 0:
        print("G3 coverage: no services/selectors modules yet (T-003) — threshold inactive")
        return 0

    covered = total_statements - total_missing
    percent = (covered / total_statements * 100) if total_statements else 100.0
    print(
        f"G3 coverage: {percent:.1f}% over {measured} business-logic files "
        f"({covered}/{total_statements} statements)"
    )
    if percent < THRESHOLD:
        print(f"G3 coverage FAILED: {percent:.1f}% < {THRESHOLD}%")
        return 1
    print("G3 coverage passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
