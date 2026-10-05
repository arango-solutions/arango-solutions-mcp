"""Canonical v3 tool result envelope and time-bounded legacy adapter."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

RESULT_CONTRACT_VERSION = "3.0"
LEGACY_RESULT_CONTRACT_SUNSET = date(2027, 2, 1)

V3_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["contractVersion", "status", "data", "error", "meta"],
    "properties": {
        "contractVersion": {"type": "string", "const": RESULT_CONTRACT_VERSION},
        "status": {"type": "string", "enum": ["success", "error"]},
        "data": {},
        "error": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["code", "message"],
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "details": {},
                    },
                },
            ]
        },
        "meta": {
            "type": "object",
            "additionalProperties": True,
            "required": ["tool"],
            "properties": {"tool": {"type": "string"}},
        },
    },
}


class ResultContractError(ValueError):
    """Raised when an expired or unknown result compatibility mode is requested."""


def _error_from_mapping(result: Mapping[str, Any]) -> tuple[str, str, Any] | None:
    direct_error = result.get("error")
    if direct_error:
        code = result.get("error_code", result.get("code", "tool_error"))
        return str(code), str(direct_error), dict(result)

    nested = result.get("result")
    if isinstance(nested, Mapping) and nested.get("error"):
        code = nested.get("error_code", nested.get("code", "tool_error"))
        return str(code), str(nested["error"]), dict(result)
    return None


def _v3_envelope(tool_name: str, result: Any) -> dict[str, Any]:
    error = _error_from_mapping(result) if isinstance(result, Mapping) else None
    if error is not None:
        code, message, details = error
        return {
            "contractVersion": RESULT_CONTRACT_VERSION,
            "status": "error",
            "data": None,
            "error": {"code": code, "message": message, "details": details},
            "meta": {"tool": tool_name},
        }
    return {
        "contractVersion": RESULT_CONTRACT_VERSION,
        "status": "success",
        "data": result,
        "error": None,
        "meta": {"tool": tool_name},
    }


def normalize_result(
    tool_name: str,
    result: Any,
    *,
    contract: str = "v3",
    today: date | None = None,
) -> Any:
    """Normalize a tool result, or return the dated v2-compatible legacy shape."""
    if contract == "v3":
        return _v3_envelope(tool_name, result)
    if contract != "legacy":
        raise ResultContractError(f"Unknown MCP result contract {contract!r}")
    current_date = today or date.today()
    if current_date >= LEGACY_RESULT_CONTRACT_SUNSET:
        raise ResultContractError(
            "The legacy MCP result contract expired on "
            f"{LEGACY_RESULT_CONTRACT_SUNSET.isoformat()}"
        )
    return result
