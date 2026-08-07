#!/usr/bin/env python3
"""Build and verify the distribution from an isolated wheel-only install."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = r"""
import importlib.metadata
import importlib.resources
import json
import pathlib
import sys
from unittest.mock import patch

root = pathlib.Path(%(root)r).resolve()
package = __import__("arangodb_mcp")
package_path = pathlib.Path(package.__file__).resolve()
assert root not in package_path.parents, (root, package_path)
assert all(pathlib.Path(item or ".").resolve() != root for item in sys.path)

catalog_resource = importlib.resources.files("arangodb_mcp.catalog").joinpath("tools.yaml")
manuals = importlib.resources.files("arangodb_mcp.manuals")
assert catalog_resource.is_file()
assert {item.name for item in manuals.iterdir() if item.name.endswith(".md")} == {
    "aql_ref.md",
    "cypher2aql.md",
    "optimization.md",
}

from arangodb_mcp.catalog.loader import load_tool_catalog
assert len(load_tool_catalog().tools) == 81

with patch("arangodb_mcp.arango_connector.ArangoClient"):
    from arangodb_mcp.server import mcp_app

manager = mcp_app._tool_manager
assert len(manager.all_registered_tools()) == 81
assert mcp_app._resource_manager._resources
assert mcp_app._prompt_manager._prompts
print(json.dumps({
    "distribution": importlib.metadata.version("arangodb-mcp-server"),
    "package": str(package_path),
    "tools": len(manager.all_registered_tools()),
    "manuals": 3,
}, sort_keys=True))
"""


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def verify(python: str) -> None:
    poetry = shutil.which("poetry")
    if poetry is None:
        raise RuntimeError("poetry is required to build the wheel")

    with tempfile.TemporaryDirectory(prefix="arangodb-mcp-wheel-") as temporary:
        work = Path(temporary)
        dist = work / "dist"
        environment = work / "venv"
        _run([poetry, "build", "--format", "wheel", "--output", str(dist)], cwd=ROOT)
        wheels = sorted(dist.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected exactly one wheel, found: {wheels}")

        _run([python, "-m", "venv", str(environment)], cwd=work)
        executable = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        _run(
            [
                str(executable),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                str(wheels[0]),
            ],
            cwd=work,
        )

        probe = work / "probe.py"
        probe.write_text(PROBE % {"root": str(ROOT)}, encoding="utf-8")
        smoke_env = os.environ.copy()
        smoke_env.update(
            {
                "ARANGO_HOSTS": "http://127.0.0.1:8529",
                "ARANGO_ROOT_USERNAME": "wheel-smoke",
                "ARANGO_ROOT_PASSWORD": "wheel-smoke-not-used",
                "PYTHONPATH": "",
            }
        )
        _run([str(executable), "-I", str(probe)], cwd=work, env=smoke_env)

        command = environment / (
            "Scripts/arangodb-mcp.exe" if os.name == "nt" else "bin/arangodb-mcp"
        )
        cli_env = os.environ.copy()
        cli_env["PYTHONPATH"] = ""
        for name in ("ARANGO_HOSTS", "ARANGO_ROOT_USERNAME", "ARANGO_ROOT_PASSWORD"):
            cli_env.pop(name, None)
        _run([str(command), "--version"], cwd=work, env=cli_env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="Python used to create the venv")
    args = parser.parse_args()
    try:
        verify(args.python)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Wheel verification failed: {exc}", file=sys.stderr)
        return 1
    print("Clean wheel build/install/import/package-data/CLI verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
