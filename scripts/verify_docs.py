#!/usr/bin/env python3
"""Fail when repository documentation drifts from executable inventory."""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _registered_tool_count() -> int:
    os.environ.setdefault("ARANGO_HOSTS", "http://localhost:8529")
    os.environ.setdefault("ARANGO_ROOT_USERNAME", "root")
    os.environ.setdefault("ARANGO_ROOT_PASSWORD", "documentation-check")
    os.environ.setdefault("ARANGO_DEFAULT_DB_NAME", "_system")
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))

    with patch("arangodb_mcp.arango_connector.ArangoClient"):
        from arangodb_mcp.server import mcp_app

    manager = cast(Any, mcp_app._tool_manager)
    return len(manager.all_registered_tools())


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
    from arangodb_mcp.config import ArangoDBSettings, EmbeddingSettings, ServerSettings

    names = {f"ARANGO_{name.upper()}" for name in ArangoDBSettings.model_fields}
    names.update(name.upper() for name in ServerSettings.model_fields)
    names.update(name.upper() for name in EmbeddingSettings.model_fields)
    return names


def _identity_env_names() -> set[str]:
    from arangodb_mcp.config import IdentitySettings

    return {name.upper() for name in IdentitySettings.model_fields}


def _observability_env_names() -> set[str]:
    from arangodb_mcp.config import ObservabilitySettings

    return {name.upper() for name in ObservabilitySettings.model_fields}


def _require(errors: list[str], content: str, marker: str, location: str) -> None:
    if marker not in content:
        errors.append(f"{location}: missing {marker!r}")


def verify() -> list[str]:
    errors: list[str] = []
    tool_count = _registered_tool_count()
    test_count = _test_function_count()

    readme = _read("README.md")
    prd = _read("PRD.md")
    server = _read("src/arangodb_mcp/server.py")
    env_example = _read(".env.example")
    compose = _read("docker-compose.yml")
    phase4_compose = _read("docker-compose.phase4.yml")
    ci = _read(".github/workflows/ci.yml")
    release = _read(".github/workflows/release.yml")
    phase4_runner = _read("scripts/run_phase4_integration.py")
    wheel_smoke = _read("scripts/verify_wheel.py")
    chart_values = _read("deploy/helm/arangodb-mcp/values.yaml")
    chart_readme = _read("deploy/helm/arangodb-mcp/README.md")
    helm_runner = _read("scripts/run_helm_kind_smoke.sh")

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
    _require(errors, prd, f"catalogs **{tool_count} tools**", "PRD.md product summary")
    _require(errors, prd, f"current count is {tool_count}", "PRD.md DOC-001")
    _require(
        errors,
        server,
        f"active of {tool_count} cataloged tools",
        "src/arangodb_mcp/server.py instructions",
    )

    for path in sorted((ROOT / "tests").glob("test_*.py")):
        _require(errors, readme, path.name, "README.md test inventory")
        _require(errors, prd, path.name, "PRD.md test inventory")
    for path in sorted((SRC / "arangodb_mcp" / "mcp_tools").glob("*.py")):
        if path.name != "__init__.py":
            _require(errors, readme, path.name, "README.md MCP tool inventory")

    for env_name in sorted(_setting_env_names()):
        for location, content in (
            ("README.md environment table", readme),
            ("PRD.md environment table", prd),
            (".env.example", env_example),
        ):
            _require(errors, content, env_name, location)

    # SEC-006/SEC-007 are already approved in the immutable PRD requirements table;
    # deployment-level identity variable names are kept consistent in operator docs.
    for env_name in sorted(_identity_env_names()):
        for location, content in (
            ("README.md environment table", readme),
            (".env.example", env_example),
        ):
            _require(errors, content, env_name, location)

    for env_name in sorted(_observability_env_names()):
        for location, content in (
            ("README.md environment table", readme),
            (".env.example", env_example),
            ("docker-compose.yml", compose),
        ):
            _require(errors, content, env_name, location)

    for marker in (
        "otel/opentelemetry-collector-contrib:0.123.0",
        "prom/prometheus:v3.2.1",
        "MCP_OIDC_ALLOW_INSECURE_HTTP",
    ):
        _require(errors, phase4_compose, marker, "docker-compose.phase4.yml")
    _require(
        errors,
        ci,
        "python scripts/run_phase4_integration.py --timeout 300",
        ".github/workflows/ci.yml",
    )
    _require(
        errors,
        ci,
        "python scripts/verify_wheel.py",
        ".github/workflows/ci.yml",
    )
    for marker in (
        "pypa/gh-action-pypi-publish@release/v1",
        "actions/attest-build-provenance@v2",
        "cosign sign --yes",
        "gh release create",
    ):
        _require(errors, release, marker, ".github/workflows/release.yml")
    for marker in ('"-I", str(probe)', "len(manager.all_registered_tools()) == 81"):
        _require(errors, wheel_smoke, marker, "scripts/verify_wheel.py")
    _require(
        errors,
        phase4_runner,
        '"down", "--volumes", "--remove-orphans"',
        "scripts/run_phase4_integration.py",
    )
    _require(
        errors,
        readme,
        "python3 scripts/run_phase4_integration.py --timeout 300",
        "README.md",
    )
    for marker in (
        "deploy/helm/arangodb-mcp",
        "scripts/verify_helm.sh",
        "scripts/run_helm_kind_smoke.sh",
        "CONTRIBUTING.md",
        "SUPPORT.md",
        "docs/threat-model.md",
        "docs/deprecation-policy.md",
    ):
        _require(errors, readme, marker, "README.md Helm/governance documentation")
    for marker in (
        "existingSecret:",
        "create:",
        "allowPrivilegeEscalation: false",
        "readOnlyRootFilesystem: true",
        "RuntimeDefault",
    ):
        _require(errors, chart_values, marker, "Helm values")
    for marker in (
        "not recommended for production",
        "helm upgrade --install",
        "helm rollback",
        "image.digest",
    ):
        _require(errors, chart_readme, marker, "Helm README")
    for marker in (
        "docker build",
        '"$KIND" load docker-image',
        '"$HELM" install',
        '"$HELM" upgrade',
        "Authenticated MCP initialize and list-databases call passed.",
        "delete cluster",
    ):
        _require(errors, helm_runner, marker, "kind Helm acceptance harness")
    for relative_path in (
        "CONTRIBUTING.md",
        "SUPPORT.md",
        "SECURITY.md",
        "docs/threat-model.md",
        "docs/deprecation-policy.md",
    ):
        content = _read(relative_path)
        _require(
            errors,
            content,
            "https://github.com/arango-solutions/arango-solutions-mcp",
            relative_path,
        )

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
