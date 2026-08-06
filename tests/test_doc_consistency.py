"""Mechanical documentation consistency gate."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_verifier():
    path = ROOT / "scripts" / "verify_docs.py"
    spec = importlib.util.spec_from_file_location("verify_docs", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_documentation_matches_executable_inventory(monkeypatch):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_docs.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    verifier = _load_verifier()
    monkeypatch.setattr(verifier, "_registered_tool_count", lambda: 82)
    errors = verifier.verify()
    assert any("README.md: missing '## Tools (82)'" in error for error in errors)
