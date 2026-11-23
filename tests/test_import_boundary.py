"""T-003 acceptance: ``academy`` ⊄ host — gate G7 must be active and able to fail.

The gate is the real ``scripts/gate_imports.py``; loading it here (instead of re-implementing
the rule) proves the thing CI runs is what the tests exercise.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _load_gate() -> Any:
    gate_path = ROOT / "scripts" / "gate_imports.py"
    spec = importlib.util.spec_from_file_location("gate_imports", gate_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


def test_gate_is_active_because_academy_exists() -> None:
    assert gate.PACKAGE.is_dir()
    assert list(gate.PACKAGE.rglob("*.py")), "G7 would pass vacuously without sources"


def test_gate_passes_on_the_current_tree(capsys: Any) -> None:
    assert gate.main() == 0

    assert "G7 import boundary passed" in capsys.readouterr().out


def test_gate_detects_a_forbidden_import(tmp_path: Path) -> None:
    leak = tmp_path / "leak.py"
    leak.write_text(
        "from host_stub.identity import Identity\n"
        "from django.contrib.auth.models import User\n"
        "import host_stub\n",
        encoding="utf-8",
    )

    found = gate.violations(leak)

    assert any("host_stub.identity" in item for item in found)
    assert any("User" in item for item in found)
    assert any("import host_stub" in item for item in found)
