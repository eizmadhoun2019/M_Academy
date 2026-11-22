"""Gate G9 — documentation check.

Fails when a canonical document is missing, a relative markdown link does not resolve, or a
retired identifier reappears (P0-/P1- task numbers, the removed §22/§24 references, ADR-015,
and the retired D-018…D-022 numbers outside their allowed history files).

Run: ``python scripts/check_docs.py``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DOCS = [
    "README.md",
    "CHARTER.md",
    "ARCHITECTURE.md",
    "RULES.md",
    "STATUS.md",
    "LOG.md",
    "docs/domain-model.md",
    "docs/api.md",
    "docs/decisions.md",
    "docs/traceability.md",
    "docs/hub-contract.md",
    "docs/configuration.md",
    "docs/background-jobs.md",
    "docs/notifications.md",
    "docs/reports.md",
    "docs/operations/environments.md",
    "docs/adr/README.md",
    "docs/performance-profile.yaml",
    "docs/ui/wireframes.md",
]

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "staticfiles",
    "local_media",
}

LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
BARE_DOC = re.compile(r"(?<![\w/.-])(docs/[A-Za-z0-9_./-]+\.(?:md|yaml))")
HTML_LINK = re.compile(r'href="([^"]+)"')

RETIRED = [
    (re.compile(r"\bP[01]-\d{2}\b"), {"docs/traceability.md", "docs/decisions.md"}),
    (re.compile(r"§\s*22\b"), set()),
    (re.compile(r"§\s*24\b"), set()),
    (re.compile(r"\bADR-015\b"), set()),
    (
        re.compile(r"\bD-0(?:18|19|20|21|22)\b"),
        {"docs/decisions.md", "docs/traceability.md", "STATUS.md", "LOG.md"},
    ),
]


def markdown_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.md"):
        if set(path.relative_to(ROOT).parts) & SKIP_DIRS:
            continue
        files.append(path)
    return sorted(files)


def resolve(source: Path, target: str) -> bool:
    target = target.split("#", 1)[0].strip()
    if not target or target.startswith(("http://", "https://", "mailto:", "tel:")):
        return True
    if target.startswith("/"):
        return (ROOT / target.lstrip("/")).exists()
    return (source.parent / target).resolve().exists() or (ROOT / target).exists()


def main() -> int:
    problems: list[str] = []

    for doc in REQUIRED_DOCS:
        if not (ROOT / doc).is_file():
            problems.append(f"missing canonical document: {doc}")

    for path in markdown_files():
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        in_fence = False
        for number, line in enumerate(text.splitlines(), start=1):
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            for target in LINK.findall(line) + HTML_LINK.findall(line) + BARE_DOC.findall(line):
                if not resolve(path, target):
                    problems.append(f"{rel}:{number}: unresolved link {target}")
            for pattern, allowed in RETIRED:
                if rel in allowed:
                    continue
                match = pattern.search(line)
                if match:
                    problems.append(f"{rel}:{number}: retired identifier {match.group(0)}")
        if in_fence:
            problems.append(f"{rel}: unbalanced code fences")

    if problems:
        print("G9 documentation check FAILED")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(f"G9 documentation check passed ({len(markdown_files())} markdown files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
