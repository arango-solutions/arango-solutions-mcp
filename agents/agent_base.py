import asyncio
import functools
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, TypeVar

from arango.database import StandardDatabase
from arango.exceptions import ArangoServerError

from arango_connector import arango_connector

SYSTEM_DB = "_system"

T = TypeVar("T")


def handle_arango_errors(
    agent_name: str,
    error_label: str = "ArangoDB",
    specific_exceptions: tuple[type[Exception], ...] = (),
    on_arango_error: Callable[[Exception], dict | None] | None = None,
):
    """Decorator that wraps an agent method with standard ArangoDB error handling.

    Catches specific ArangoDB exceptions first (with error_label prefix),
    then ArangoServerError, then any unexpected Exception. Returns a
    standardized error dict in all cases.

    Args:
        agent_name: Name used in log messages (e.g. "CollectionManagementAgent").
        error_label: Prefix for the error message (e.g. "ArangoDB Collection").
        specific_exceptions: Tuple of exception classes to catch before ArangoServerError.
        on_arango_error: Optional callback invoked with the caught exception when
            a handled error occurs. If it returns a dict, that dict is used as the
            response (short-circuiting the standard error format). If it returns
            None, the standard error format is returned. The error is still logged
            before the callback fires.
    """
    all_exceptions = specific_exceptions + (ArangoServerError,)

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, mcp_tool_inputs, *args, **kwargs):
            _logger = logging.getLogger(func.__module__)
            try:
                return await func(self, mcp_tool_inputs, *args, **kwargs)
            except all_exceptions as e:
                _logger.error(f"{agent_name}: ArangoDB error - {e}")
                if on_arango_error is not None:
                    override = on_arango_error(e)
                    if override is not None:
                        return override
                return {
                    "error": f"{error_label} Error: {getattr(e, 'error_message', str(e))}",
                    "error_code": getattr(e, "error_code", None),
                }
            except Exception as e:
                _logger.error(f"{agent_name}: Unexpected error - {e}", exc_info=True)
                if on_arango_error is not None:
                    override = on_arango_error(e)
                    if override is not None:
                        return override
                return {"error": f"An unexpected error occurred: {str(e)}"}

        return wrapper

    return decorator


class ArangoAgentBase(ABC):
    """Base class for ArangoDB operation agents.

    Pure data connector - no LLM dependencies.
    The external LLM (Cursor/Claude) handles intelligence.
    """

    def resolve_db(self, database_name: Optional[str] = None) -> tuple[StandardDatabase, str]:
        """Get an authenticated database handle and its resolved name.

        Returns:
            A tuple of (database_handle, resolved_database_name).
        """
        db = arango_connector.get_db(database_name)
        resolved_name = database_name or db.name
        return db, resolved_name

    @staticmethod
    def pack_optional(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Copy non-None values from kwargs into payload, return payload.

        Reduces the repeated pattern:
            if x is not None: payload["x"] = x
        """
        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v
        return payload

    @staticmethod
    async def run_sync(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run a synchronous function in a thread to avoid blocking the event loop.

        Use this for python-arango calls that perform network I/O.
        """
        return await asyncio.to_thread(func, *args, **kwargs)

    @abstractmethod
    async def arun(self, mcp_tool_inputs: dict[str, Any]) -> dict[str, Any]:
        """
        The core logic for this agent.
        'mcp_tool_inputs' are the validated arguments received by the MCP tool.
        This method should perform the ArangoDB operation and return a result dictionary.
        """
        pass
