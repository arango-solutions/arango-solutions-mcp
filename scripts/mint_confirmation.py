#!/usr/bin/env python3
"""Mint a short-lived irreversible-action confirmation outside the MCP surface."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from arangodb_mcp.policy.confirmation import mint_confirmation_token


def _arguments(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("arguments JSON must be an object")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mint an actor/action/parameter-bound one-use MCP confirmation token."
    )
    parser.add_argument("--actor", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--arguments-json", required=True, type=_arguments)
    parser.add_argument("--ttl-seconds", type=int, default=120)
    args = parser.parse_args()

    secret = os.environ.get("MCP_CONFIRMATION_SECRET", "")
    if not secret:
        parser.error("MCP_CONFIRMATION_SECRET must be set in the trusted operator environment")
    token = mint_confirmation_token(
        secret=secret,
        actor=args.actor,
        action=args.action,
        arguments=args.arguments_json,
        ttl_seconds=args.ttl_seconds,
    )
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
