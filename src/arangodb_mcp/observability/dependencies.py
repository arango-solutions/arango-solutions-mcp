"""Dependency instrumentation shared by agents, tools, and connector lifecycle."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, TypeVar

from opentelemetry.trace import Status, StatusCode

from arangodb_mcp.observability.context import get_request_id
from arangodb_mcp.observability.conventions import (
    ATTR_CONVENTION_VERSION,
    ATTR_DB_OPERATION,
    ATTR_OUTCOME,
    ATTR_REQUEST_ID,
    CONVENTION_VERSION,
    SPAN_ARANGO_DATABASE,
)
from arangodb_mcp.observability.metrics import dependency_finished, dependency_started
from arangodb_mcp.observability.telemetry import get_tracer

T = TypeVar("T")

_ARANGO_OPERATIONS = frozenset(
    {
        "abort_transaction",
        "add_index",
        "begin_transaction",
        "collection",
        "collections",
        "commit_transaction",
        "create_analyzer",
        "create_collection",
        "create_database",
        "create_graph",
        "create_user",
        "create_view",
        "databases",
        "delete",
        "delete_analyzer",
        "delete_collection",
        "delete_database",
        "delete_graph",
        "delete_index",
        "delete_user",
        "delete_view",
        "execute",
        "explain",
        "get",
        "graph",
        "graphs",
        "has_collection",
        "has_database",
        "has_graph",
        "indexes",
        "insert",
        "permissions",
        "properties",
        "replace",
        "transactions",
        "update",
        "users",
        "validate",
        "version",
    }
)


def arango_operation(func: Callable[..., Any]) -> str:
    name = getattr(func, "__name__", "")
    if name == "_connect_sync":
        return "connect"
    if name == "health_check":
        return "health"
    return name if name in _ARANGO_OPERATIONS else "other"


async def run_arango_sync(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a driver call in a context-copying worker under one database span."""
    operation = arango_operation(func)
    started = time.perf_counter()
    outcome = "error"
    dependency_started("arangodb", operation)
    with get_tracer().start_as_current_span(
        SPAN_ARANGO_DATABASE,
        attributes={
            ATTR_CONVENTION_VERSION: CONVENTION_VERSION,
            ATTR_REQUEST_ID: get_request_id() or "",
            ATTR_DB_OPERATION: operation,
        },
    ) as span:
        try:
            result = await asyncio.to_thread(func, *args, **kwargs)
            outcome = "success"
            span.set_attribute(ATTR_OUTCOME, outcome)
            return result
        except Exception as exc:
            span.record_exception(exc)
            span.set_attribute(ATTR_OUTCOME, outcome)
            span.set_status(Status(StatusCode.ERROR))
            raise
        finally:
            dependency_finished("arangodb", operation, outcome, time.perf_counter() - started)


def run_arango_inline(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Instrument a synchronous connector call already running off-loop."""
    operation = arango_operation(func)
    started = time.perf_counter()
    outcome = "error"
    dependency_started("arangodb", operation)
    with get_tracer().start_as_current_span(
        SPAN_ARANGO_DATABASE,
        attributes={
            ATTR_CONVENTION_VERSION: CONVENTION_VERSION,
            ATTR_REQUEST_ID: get_request_id() or "",
            ATTR_DB_OPERATION: operation,
        },
    ) as span:
        try:
            result = func(*args, **kwargs)
            outcome = "success"
            span.set_attribute(ATTR_OUTCOME, outcome)
            return result
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR))
            raise
        finally:
            dependency_finished("arangodb", operation, outcome, time.perf_counter() - started)
