import functools
import logging
from abc import ABC, abstractmethod
from typing import Any

from arango.exceptions import ArangoServerError


def handle_arango_errors(
    agent_name: str,
    error_label: str = "ArangoDB",
    specific_exceptions: tuple[type[Exception], ...] = (),
):
    """Decorator that wraps an agent method with standard ArangoDB error handling.

    Catches specific ArangoDB exceptions first (with error_label prefix),
    then ArangoServerError, then any unexpected Exception. Returns a
    standardized error dict in all cases.

    Args:
        agent_name: Name used in log messages (e.g. "CollectionManagementAgent").
        error_label: Prefix for the error message (e.g. "ArangoDB Collection").
        specific_exceptions: Tuple of exception classes to catch before ArangoServerError.
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
                return {
                    "error": f"{error_label} Error: {getattr(e, 'error_message', str(e))}",
                    "error_code": getattr(e, "error_code", None),
                }
            except Exception as e:
                _logger.error(f"{agent_name}: Unexpected error - {e}", exc_info=True)
                return {"error": f"An unexpected error occurred: {str(e)}"}

        return wrapper

    return decorator


class ArangoAgentBase(ABC):
    """Base class for ArangoDB operation agents.

    Pure data connector - no LLM dependencies.
    The external LLM (Cursor/Claude) handles intelligence.
    """

    @abstractmethod
    async def arun(self, mcp_tool_inputs: dict[str, Any]) -> dict[str, Any]:
        """
        The core logic for this agent.
        'mcp_tool_inputs' are the validated arguments received by the MCP tool.
        This method should perform the ArangoDB operation and return a result dictionary.
        """
        pass
