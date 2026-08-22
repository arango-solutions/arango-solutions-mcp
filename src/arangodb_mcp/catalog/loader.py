"""Load and validate the canonical MCP tool catalog."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

import yaml

CATALOG_RESOURCE = resources.files("arangodb_mcp.catalog").joinpath("tools.yaml")
_RISK_VALUES = frozenset({"low", "medium", "high", "critical"})
_OPERATION_VALUES = frozenset({"read", "write", "admin"})
_CONFIRMATION_VALUES = frozenset({"none", "conditional", "human"})
_REQUIRED_FIELDS = frozenset(
    {"name", "category", "risk", "operation", "scope", "limits", "confirmation"}
)


class CatalogError(ValueError):
    """Raised when the checked-in tool catalog is incomplete or invalid."""


@dataclass(frozen=True)
class ToolLimits:
    max_runtime_ms: int
    max_rows: int
    max_response_bytes: int
    max_bulk_items: int
    max_concurrency: int


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    category: str
    risk: str
    operation: str
    scope: str
    limits: ToolLimits
    confirmation: str
    limit_class: str = "standard"


@dataclass(frozen=True)
class ToolCatalog:
    version: int
    tools: Mapping[str, ToolDefinition]

    def get(self, name: str) -> ToolDefinition:
        try:
            return self.tools[name]
        except KeyError as exc:
            raise CatalogError(f"Tool {name!r} is not present in catalog/tools.yaml") from exc

    def validate_registered(self, names: Iterable[str]) -> None:
        registered = set(names)
        cataloged = set(self.tools)
        unknown = sorted(registered - cataloged)
        missing = sorted(cataloged - registered)
        if unknown or missing:
            details = []
            if unknown:
                details.append(f"unknown registered tools: {', '.join(unknown)}")
            if missing:
                details.append(f"catalog tools not registered: {', '.join(missing)}")
            raise CatalogError("; ".join(details))


def _positive_int(value: Any, field: str, policy: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CatalogError(f"Limit policy {policy!r} field {field!r} must be a positive integer")
    return value


def _load_limits(raw: Any) -> dict[str, ToolLimits]:
    if not isinstance(raw, dict) or not raw:
        raise CatalogError("limit_policies must be a non-empty mapping")
    required = {
        "max_runtime_ms",
        "max_rows",
        "max_response_bytes",
        "max_bulk_items",
        "max_concurrency",
    }
    policies: dict[str, ToolLimits] = {}
    for name, values in raw.items():
        if not isinstance(name, str) or not name:
            raise CatalogError("Limit policy names must be non-empty strings")
        if not isinstance(values, dict) or set(values) != required:
            raise CatalogError(f"Limit policy {name!r} must define exactly {sorted(required)}")
        policies[name] = ToolLimits(
            **{field: _positive_int(values[field], field, name) for field in required}
        )
    return policies


def load_tool_catalog(path: Path | None = None) -> ToolCatalog:
    """Load the catalog and fail closed on malformed or duplicate entries."""
    try:
        source = CATALOG_RESOURCE if path is None else path
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        location = "packaged catalog/tools.yaml" if path is None else str(path)
        raise CatalogError(f"Unable to load tool catalog at {location}: {exc}") from exc

    if not isinstance(document, dict):
        raise CatalogError("Tool catalog root must be a mapping")
    if document.get("version") != 1:
        raise CatalogError("Tool catalog version must be 1")

    limits = _load_limits(document.get("limit_policies"))
    raw_tools = document.get("tools")
    if not isinstance(raw_tools, list) or not raw_tools:
        raise CatalogError("tools must be a non-empty list")

    tools: dict[str, ToolDefinition] = {}
    for index, raw in enumerate(raw_tools):
        if not isinstance(raw, dict) or set(raw) != _REQUIRED_FIELDS:
            raise CatalogError(f"Tool entry {index} must define exactly {sorted(_REQUIRED_FIELDS)}")
        if not all(isinstance(raw[field], str) and raw[field] for field in _REQUIRED_FIELDS):
            raise CatalogError(f"Tool entry {index} fields must be non-empty strings")
        name = raw["name"]
        if name in tools:
            raise CatalogError(f"Duplicate tool catalog entry: {name}")
        if raw["risk"] not in _RISK_VALUES:
            raise CatalogError(f"Tool {name!r} has invalid risk {raw['risk']!r}")
        if raw["operation"] not in _OPERATION_VALUES:
            raise CatalogError(f"Tool {name!r} has invalid operation {raw['operation']!r}")
        if raw["confirmation"] not in _CONFIRMATION_VALUES:
            raise CatalogError(
                f"Tool {name!r} has invalid confirmation policy {raw['confirmation']!r}"
            )
        try:
            limit_policy = limits[raw["limits"]]
        except KeyError as exc:
            raise CatalogError(
                f"Tool {name!r} references unknown limit policy {raw['limits']!r}"
            ) from exc
        tools[name] = ToolDefinition(
            name=name,
            category=raw["category"],
            risk=raw["risk"],
            operation=raw["operation"],
            scope=raw["scope"],
            limits=limit_policy,
            confirmation=raw["confirmation"],
            limit_class=raw["limits"],
        )

    return ToolCatalog(version=1, tools=MappingProxyType(tools))
