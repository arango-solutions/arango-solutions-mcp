#!/usr/bin/env python3
"""Track pattern-search results until the agent attributes actual reuse.

This hook never calls ``pattern-applied`` itself: surfacing is not proof of use.
It records candidate keys per Cursor conversation and injects a precise reminder.
The stop hook then asks for one attribution pass when searched patterns remain
unaccounted for.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from typing import Any

STATE_DIR = os.path.join(".cursor", ".shared-memory-sessions")


def _event_id(payload: dict[str, Any]) -> str:
    raw = payload.get("conversation_id") or payload.get("generation_id") or "unknown"
    return re.sub(r"[^A-Za-z0-9_.-]", "-", str(raw))[:120]


def _state_path(payload: dict[str, Any]) -> str:
    return os.path.join(STATE_DIR, f"{_event_id(payload)}.json")


def _load(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            value = json.load(fh)
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(path: str, state: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".apply-", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)
        os.replace(tmp, path)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _json_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _pattern_keys(value: Any) -> list[str]:
    """Collect returned pattern ``_key`` values from nested MCP envelopes."""
    value = _json_value(value)
    found: list[str] = []
    if isinstance(value, dict):
        key = value.get("_key")
        if isinstance(key, str) and key:
            found.append(key)
        for child in value.values():
            found.extend(_pattern_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_pattern_keys(child))
    # Stable de-duplication protects against envelopes repeating the same result.
    return list(dict.fromkeys(found))


def _tool_kind(name: Any) -> str:
    normalized = str(name or "").lower().replace("_", "-")
    if normalized.endswith("pattern-applied"):
        return "applied"
    if normalized.endswith("pattern-search"):
        return "search"
    return ""


def update_state(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    path = _state_path(payload)
    state = _load(path)
    kind = _tool_kind(payload.get("tool_name"))
    newly_surfaced: list[str] = []

    if kind == "search":
        newly_surfaced = _pattern_keys(
            payload.get("tool_output", payload.get("result_json", payload.get("tool_response")))
        )
        if newly_surfaced:
            state.setdefault("surfaced_keys", [])
            state["surfaced_keys"] = list(
                dict.fromkeys([*state["surfaced_keys"], *newly_surfaced])
            )
            tool_input = _json_value(payload.get("tool_input") or {})
            if isinstance(tool_input, dict) and tool_input.get("query_text"):
                state["last_query"] = str(tool_input["query_text"])[:300]
    elif kind == "applied":
        tool_input = _json_value(payload.get("tool_input") or {})
        keys = tool_input.get("keys", []) if isinstance(tool_input, dict) else []
        if isinstance(keys, list):
            state.setdefault("applied_keys", [])
            state["applied_keys"] = list(
                dict.fromkeys([*state["applied_keys"], *[k for k in keys if isinstance(k, str)]])
            )

    if state:
        state["conversation_id"] = _event_id(payload)
        _save(path, state)
    return state, newly_surfaced


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        _, surfaced = update_state(payload)
    except Exception:  # noqa: BLE001 - telemetry must never break tool use
        print("{}")
        return 0

    if surfaced:
        keys = ", ".join(surfaced)
        context = (
            "[SHARED-MEMORY APPLY GATE] Search surfaced these candidate keys: "
            f"{keys}. If you actually reuse any result, you MUST call pattern-applied "
            "with only the reused key(s). Do not mark merely viewed results as applied."
        )
        print(json.dumps({"additional_context": context}))
    else:
        print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
