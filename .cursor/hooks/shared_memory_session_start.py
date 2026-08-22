#!/usr/bin/env python3
"""Cursor sessionStart adapter for the shared-memory digest.

The canonical digest implementation is shared with Claude Code. Cursor requires
JSON with ``additional_context`` instead of treating plain stdout as context.
Any failure returns an empty object so session creation always remains fail-open.
"""

from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    try:
        json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        print("{}")
        return 0

    try:
        proc = subprocess.run(
            [sys.executable, ".claude/hooks/session_recall.py"],
            capture_output=True,
            text=True,
            timeout=13,
            check=False,
        )
        context = proc.stdout.strip()
    except Exception:  # noqa: BLE001
        context = ""

    print(json.dumps({"additional_context": context} if context else {}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
