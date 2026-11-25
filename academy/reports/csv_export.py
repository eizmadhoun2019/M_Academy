"""CSV writing rules — ``docs/reports.md`` §5.

Three things must be true of every file: Excel opens Arabic (UTF-8 BOM), a spreadsheet cannot
execute a cell as a formula, and a missing value is an empty cell instead of the string
``None``. The streamer never holds more than one row group in memory.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

BOM = "\ufeff"
LINE_END = "\r\n"
#: A cell that begins with one of these is data a spreadsheet would evaluate.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_CHUNK_ROWS = 500


def neutralize(value: str) -> str:
    """Prefix a would-be formula with ``'`` so the cell stays text (§5)."""
    return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value


def format_cell(value: Any) -> str:
    """One cell, formatted by type rather than by locale (§5)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        moment = value if value.tzinfo else value.replace(tzinfo=UTC)
        return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def cells(row: Mapping[str, Any], columns: Sequence[str]) -> list[str]:
    return [neutralize(format_cell(row[column])) for column in columns]


def stream(rows: Iterable[Mapping[str, Any]], columns: Sequence[str]) -> Iterable[str]:
    """Yield the BOM, the header row and then the rows, CRLF-delimited (§5)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator=LINE_END)
    writer.writerow(columns)
    yield BOM + buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    pending = 0
    for row in rows:
        writer.writerow(cells(row, columns))
        pending += 1
        if pending >= _CHUNK_ROWS:
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            pending = 0
    if pending:
        yield buffer.getvalue()


def filename(start: Any = None, end: Any = None) -> str:
    """``academy-completion-<from>-<to>.csv``; a missing bound is ``all`` (§5)."""
    return f"academy-completion-{start or 'all'}-{end or 'all'}.csv"
