#!/usr/bin/env python3
"""Fail when repository documentation drifts from executable inventory."""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _registered_tool_count() -> int:
    os.environ.setdefault("ARANGO_HOSTS", "http://localhost:8529")
    os.environ.setdefault("ARANGO_ROOT_USERNAME", "root")
    os.environ.setdefault("ARANGO_ROOT_PASSWORD", "documentation-check")
    os.environ.setdefault("ARANGO_DEFAULT_DB_NAME", "_system")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    with patch("arango_connector.ArangoClient"):
        from server import mcp_app

    return len(mcp_app._tool_manager.list_tools())


def _test_function_count() -> int:
    count = 0
    for path in (ROOT / "tests").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        count += sum(
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name.startswith("test_")
            for node in ast.walk(tree)
        )
    return count


def _setting_env_names() -> set[str]:
    from config import ArangoDBSettings, EmbeddingSettings, ServerSettings

    names = {f"ARANGO_{name.upper()}" for name in ArangoDBSettings.model_fields}
    names.update(name.upper() for name in ServerSettings.model_fields)
    names.update(name.upper() for name in EmbeddingSettings.model_fields)
    return names


def _require(errors: list[str], content: str, marker: str, location: str) -> None:
    if marker not in content:
        errors.append(f"{location}: missing {marker!r}")


def verify() -> list[str]:
    errors: list[str] = []
    tool_count = _registered_tool_count()
    test_count = _test_function_count()

    readme = _read("README.md")
    prd = _read("PRD.md")
    scorecard = _read("SCORECARD.md")
    server = _read("server.py")
    env_example = _read(".env.example")

    _require(errors, readme, f"## Tools ({tool_count})", "README.md")
    _require(
        errors,
        readme,
        f"Pytest suite ({test_count} test functions)",
        "README.md architecture tree",
    )
    _require(
        errors,
        readme,
        f"Self-testing** — {test_count} test functions",
        "README.md key features",
    )
    _require(errors, prd, f"exposes **{tool_count} tools**", "PRD.md product summary")
    _require(errors, prd, f"current count is {tool_count}", "PRD.md DOC-001")
    _require(
        errors,
        scorecard,
        f"contains {test_count} test functions",
        "SCORECARD.md reliability evidence",
    )
    _require(errors, server, f"CAPABILITIES ({tool_count} tools):", "server.py instructions")

    for path in sorted((ROOT / "tests").glob("test_*.py")):
        _require(errors, readme, path.name, "README.md test inventory")
        _require(errors, prd, path.name, "PRD.md test inventory")
    for path in sorted((ROOT / "mcp_tools").glob("*.py")):
        if path.name != "__init__.py":
            _require(errors, readme, path.name, "README.md MCP tool inventory")

    for env_name in sorted(_setting_env_names()):
        for location, content in (
            ("README.md environment table", readme),
            ("PRD.md environment table", prd),
            (".env.example", env_example),
        ):
            _require(errors, content, env_name, location)

    if "(uncommitted)" in prd:
        errors.append("PRD.md release history contains '(uncommitted)'")

    return errors


def main() -> int:
    errors = verify()
    if errors:
        print("Documentation consistency check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "Documentation consistency check passed: "
        f"{_registered_tool_count()} tools, {_test_function_count()} test functions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
