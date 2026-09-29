"""Lightweight console entry point for the packaged server."""

from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
from typing import Sequence


def _version() -> str:
    try:
        return version("arangodb-mcp-server")
    except PackageNotFoundError:
        return "unknown"


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="arangodb-mcp", description="Run the ArangoDB MCP server")
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version()}")
    parser.parse_args(argv)

    from arangodb_mcp.main import run_server_cli

    run_server_cli([])


if __name__ == "__main__":
    main()
