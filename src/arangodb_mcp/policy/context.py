"""Immutable startup policy context used by tool registration and dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ServerPolicySettings(Protocol):
    mcp_profile: str
    mcp_toolsets: str
    mcp_denied_tools: str
    mcp_denied_categories: str
    mcp_result_contract: str


def _csv_set(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class PolicyContext:
    profile: str
    toolsets: frozenset[str]
    denied_tools: frozenset[str]
    denied_categories: frozenset[str]
    result_contract: str

    @classmethod
    def from_settings(cls, server_settings: ServerPolicySettings) -> PolicyContext:
        return cls(
            profile=str(server_settings.mcp_profile),
            toolsets=_csv_set(str(server_settings.mcp_toolsets)),
            denied_tools=_csv_set(str(server_settings.mcp_denied_tools)),
            denied_categories=_csv_set(str(server_settings.mcp_denied_categories)),
            result_contract=str(server_settings.mcp_result_contract),
        )
