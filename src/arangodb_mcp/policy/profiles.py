"""Deterministic startup profile and denylist resolution."""

from __future__ import annotations

from dataclasses import dataclass

from arangodb_mcp.catalog.loader import ToolCatalog
from arangodb_mcp.policy.context import PolicyContext

BASE_PROFILES = frozenset({"readonly", "developer", "operator", "admin"})
ADDITIVE_TOOLSETS = frozenset({"graph", "search"})

_CORE_CATEGORIES = frozenset(
    {"aql", "cluster", "collection", "database", "document", "index", "manual"}
)
_DEVELOPER_CATEGORIES = _CORE_CATEGORIES | {"memory", "transaction"}
_OPERATOR_CATEGORIES = _DEVELOPER_CATEGORIES | {"backup"}


class PolicyError(ValueError):
    """Raised when startup policy would silently expose or fail to deny tools."""


@dataclass(frozen=True)
class ProfileSelection:
    profile: str
    toolsets: frozenset[str]
    denied_tools: frozenset[str]
    denied_categories: frozenset[str]
    active_tools: frozenset[str]


def _allowed_operations(profile: str) -> frozenset[str]:
    if profile == "readonly":
        return frozenset({"read"})
    if profile == "developer":
        return frozenset({"read", "write"})
    return frozenset({"read", "write", "admin"})


def _base_categories(profile: str, all_categories: frozenset[str]) -> frozenset[str]:
    if profile == "readonly":
        return _CORE_CATEGORIES
    if profile == "developer":
        return _DEVELOPER_CATEGORIES
    if profile == "operator":
        return _OPERATOR_CATEGORIES
    return all_categories


def resolve_tool_inventory(catalog: ToolCatalog, context: PolicyContext) -> ProfileSelection:
    """Resolve the exact externally visible tool inventory and fail on policy typos."""
    if context.profile not in BASE_PROFILES:
        raise PolicyError(
            f"Unknown MCP profile {context.profile!r}; expected one of {sorted(BASE_PROFILES)}"
        )

    unknown_toolsets = context.toolsets - ADDITIVE_TOOLSETS
    if unknown_toolsets:
        raise PolicyError(f"Unknown MCP additive toolsets: {sorted(unknown_toolsets)}")

    catalog_names = frozenset(catalog.tools)
    all_categories = frozenset(tool.category for tool in catalog.tools.values())
    unknown_denied_tools = context.denied_tools - catalog_names
    if unknown_denied_tools:
        raise PolicyError(f"Unknown denied MCP tools: {sorted(unknown_denied_tools)}")
    unknown_denied_categories = context.denied_categories - all_categories
    if unknown_denied_categories:
        raise PolicyError(f"Unknown denied MCP categories: {sorted(unknown_denied_categories)}")

    categories = set(_base_categories(context.profile, all_categories))
    categories.update(context.toolsets)
    operations = _allowed_operations(context.profile)
    active = {
        tool.name
        for tool in catalog.tools.values()
        if tool.category in categories and tool.operation in operations
    }
    active.difference_update(context.denied_tools)
    active = {
        name for name in active if catalog.tools[name].category not in context.denied_categories
    }
    return ProfileSelection(
        profile=context.profile,
        toolsets=context.toolsets,
        denied_tools=context.denied_tools,
        denied_categories=context.denied_categories,
        active_tools=frozenset(active),
    )
