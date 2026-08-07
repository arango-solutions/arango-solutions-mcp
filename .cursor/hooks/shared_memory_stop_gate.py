#!/usr/bin/env python3
"""Cursor stop gate for PRD drift."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any

STATE_DIR = os.path.join(".cursor", ".shared-memory-sessions")


def _event_id(payload: dict[str, Any]) -> str:
    raw = payload.get("conversation_id") or payload.get("generation_id") or "unknown"
    return re.sub(r"[^A-Za-z0-9_.-]", "-", str(raw))[:120]


def _state_path(payload: dict[str, Any]) -> str:
    return os.path.join(STATE_DIR, f"{_event_id(payload)}.json")


def _pending_keys(payload: dict[str, Any]) -> list[str]:
    try:
        with open(_state_path(payload), encoding="utf-8") as fh:
            state = json.load(fh)
        surfaced = state.get("surfaced_keys", [])
        applied = set(state.get("applied_keys", []))
        return [key for key in surfaced if key not in applied]
    except (OSError, json.JSONDecodeError, AttributeError):
        return []


def _drift_counts() -> tuple[int, int]:
    if os.path.exists(".no-drift-gate"):
        return 0, 0
    try:
        names = os.listdir(".prd-drift-queue")
    except OSError:
        return 0, 0
    return len(names), sum(name.startswith("prd_") for name in names)


def _mine_capture_candidates(payload: dict[str, Any]) -> None:
    """Best-effort reuse of the Claude miner when transcript shapes are compatible."""
    try:
        subprocess.run(
            [sys.executable, ".claude/hooks/capture_candidates.py"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=7,
            check=False,
        )
    except Exception:  # noqa: BLE001
        pass


def _cleanup_state(payload: dict[str, Any]) -> None:
    try:
        os.remove(_state_path(payload))
    except OSError:
        pass


def followup(payload: dict[str, Any]) -> str:
    drift_count, prd_count = _drift_counts()
    parts: list[str] = []

    if drift_count:
        extra = f", including {prd_count} PRD edit(s)" if prd_count else ""
        parts.append(
            f"[PRD-DRIFT GATE] {drift_count} change(s) are queued{extra}. "
            "Run /prd-sync now; it audits the changes and clears the queue."
        )
    return " ".join(parts)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        print("{}")
        return 0

    _mine_capture_candidates(payload)
    loop_count = payload.get("loop_count", 0)
    if not isinstance(loop_count, int) or loop_count > 0:
        _cleanup_state(payload)
        print("{}")
        return 0

    message = followup(payload)
    # Attribution reminders are injected immediately after pattern-search by
    # shared_memory_apply_tracker.py. Stop-time enforcement caused loops when
    # surfaced results were intentionally reviewed but not applied.
    _cleanup_state(payload)
    print(json.dumps({"followup_message": message} if message else {}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
