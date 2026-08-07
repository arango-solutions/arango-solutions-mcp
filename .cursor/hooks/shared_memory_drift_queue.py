#!/usr/bin/env python3
"""Cursor afterFileEdit adapter for the canonical PRD drift queue hook."""

from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        file_path = payload.get("file_path") or ""
    except Exception:  # noqa: BLE001
        file_path = ""

    if file_path:
        try:
            subprocess.run(
                [sys.executable, ".claude/hooks/drift_queue.py"],
                input=json.dumps({"tool_input": {"file_path": file_path}}),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass

    # afterFileEdit has no supported output fields; still emit valid JSON.
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
