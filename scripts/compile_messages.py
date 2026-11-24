"""Compile the tracked ``.po`` catalogues into Django's ``.mo`` files.

Django reads compiled catalogues only, and the images and CI runners do not ship GNU
``msgfmt``. This script writes the same format with the standard library, so a checkout stays
buildable everywhere and the binary files never need to be committed.

Usage: ``python scripts/compile_messages.py locale/ar`` (one or more locale directories).
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

HEADER = "Content-Type: text/plain; charset=UTF-8\nContent-Transfer-Encoding: 8bit\n"


def _unescape(value: str) -> str:
    out: list[str] = []
    escaped = False
    for char in value:
        if escaped:
            out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(char, char))
            escaped = False
        elif char == "\\":
            escaped = True
        else:
            out.append(char)
    return "".join(out)


def parse_po(path: Path) -> dict[str, str]:
    """Read the ``msgid``/``msgstr`` pairs of one catalogue, keeping comments out."""
    entries: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    target: list[str] = []

    def flush() -> None:
        nonlocal current, buffer
        if current is not None:
            entries[current] = "".join(buffer)
        current = None
        buffer = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("msgid "):
            flush()
            target = ["msgid"]
            current = _unescape(line[len("msgid ") :].strip().strip('"'))
        elif line.startswith("msgstr "):
            target = ["msgstr"]
            buffer = [_unescape(line[len("msgstr ") :].strip().strip('"'))]
        elif line.startswith('"') and line.endswith('"') and target:
            piece = _unescape(line[1:-1])
            if target == ["msgid"]:
                current = (current or "") + piece
            else:
                buffer.append(piece)
    flush()
    return entries


def write_mo(entries: dict[str, str], path: Path) -> None:
    """Write one binary catalogue; the layout is the one ``msgfmt`` produces."""
    items = [(key.encode("utf-8"), value.encode("utf-8")) for key, value in entries.items()]
    items.sort(key=lambda item: item[0])
    count = len(items)

    key_start = 7 * 4
    value_start = key_start + count * 8
    strings_start = value_start + count * 8
    key_block = b"".join(key + b"\x00" for key, _ in items)

    offsets: list[int] = []
    cursor = strings_start + len(key_block)
    for _, value in items:
        offsets.append(cursor)
        cursor += len(value) + 1

    output = bytearray()
    output += struct.pack("Iiiiiii", 0x950412DE, 0, count, key_start, value_start, 0, 0)
    position = strings_start
    for key, _ in items:
        output += struct.pack("ii", len(key), position)
        position += len(key) + 1
    for (_, value), offset in zip(items, offsets, strict=True):
        output += struct.pack("ii", len(value), offset)
    output += key_block
    for _, value in items:
        output += value + b"\x00"

    path.write_bytes(bytes(output))


def compile_locale(directory: Path) -> Path:
    source = directory / "LC_MESSAGES" / "django.po"
    entries = parse_po(source)
    header = entries.pop("", HEADER)
    entries[""] = header
    target = directory / "LC_MESSAGES" / "django.mo"
    write_mo(entries, target)
    return target


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: compile_messages.py <locale directory> [...]", file=sys.stderr)
        return 2
    for argument in argv:
        directory = Path(argument)
        if not (directory / "LC_MESSAGES" / "django.po").is_file():
            print(f"no catalogue at {directory}", file=sys.stderr)
            return 1
        target = compile_locale(directory)
        print(f"compiled {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
