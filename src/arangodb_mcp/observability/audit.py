"""Single-boundary, redacted catalog mutation audit events."""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping

from arangodb_mcp.observability.context import get_request_id, get_trace_id
from arangodb_mcp.policy.actor_context import get_actor_id

logger = logging.getLogger("audit.catalog")

_TARGET_KEYS = (
    "database_name",
    "collection_name",
    "graph_name",
    "edge_collection_name",
    "view_name",
    "analyzer_name",
    "username",
    "target_username",
    "document_key",
    "document_key_or_id",
    "transaction_id",
    "backup_id",
)


def build_target(definition: Any, arguments: Mapping[str, Any]) -> dict[str, str]:
    """Extract only identifier fields; payloads and query text are never inspected."""
    target = {"scope": str(definition.scope), "category": str(definition.category)}
    for key in _TARGET_KEYS:
        value = arguments.get(key)
        if isinstance(value, str) and value:
            target[key] = value[:256]
    return target


def emit_catalog_audit(
    *,
    definition: Any,
    action: str,
    arguments: Mapping[str, Any],
    outcome: str,
) -> None:
    """Emit exactly one allow-listed event for a write/admin dispatch attempt."""
    event = {
        "event": "catalog_action",
        "actor": get_actor_id(),
        "action": action,
        "target": build_target(definition, arguments),
        "outcome": outcome,
        "correlation_id": get_request_id(),
        "trace_id": get_trace_id(),
    }
    logger.info(
        json.dumps(event, separators=(",", ":"), ensure_ascii=True),
        extra={"audit_event": event},
    )
