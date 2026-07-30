"""Shared helpers for the embedding / pattern-memory MCP tools.

The 74 core tools delegate to agent classes (``agents/``) that provide two
guarantees the rest of the server relies on:

* every blocking python-arango call runs off the event loop
  (``ArangoAgentBase.run_sync`` -> ``asyncio.to_thread``); and
* every failure returns a standardized error envelope
  (``agents.agent_base.handle_arango_errors``).

The embedding / pattern-memory tools are implemented directly in the tool layer
(they have no agent), so they use the helpers below to provide the SAME two
guarantees without a signature-changing decorator that would interfere with
FastMCP's parameter introspection:

* ``run_sync(fn, *a, **kw)``      -> await a blocking call in a worker thread;
* ``arango_error_result(exc)``    -> the standardized
  ``{"result": {"error": ..., "error_code": ...}}`` envelope, matching
  ``handle_arango_errors`` so all tools speak one error shape.
"""

import asyncio
import logging
from typing import Any, Callable, TypeVar

from arango.exceptions import ArangoServerError

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def run_sync(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a blocking python-arango call in a worker thread.

    Mirrors ``ArangoAgentBase.run_sync`` so the embedding / pattern-memory tools
    never block the FastMCP event loop with driver network I/O.
    """
    return await asyncio.to_thread(func, *args, **kwargs)


def arango_error_result(exc: Exception, error_label: str = "ArangoDB") -> dict:
    """Return the standardized tool-layer error envelope for ``exc``.

    Mirrors ``agents.agent_base.handle_arango_errors``: an ``ArangoServerError``
    yields ``{"error": "<label> Error: ...", "error_code": <n>}``; anything else
    yields the generic unexpected-error message. The dict is wrapped in
    ``{"result": ...}`` to match the tool-layer response shape.
    """
    if isinstance(exc, ArangoServerError):
        logger.error("%s error: %s", error_label, exc)
        return {
            "result": {
                "error": f"{error_label} Error: {getattr(exc, 'error_message', str(exc))}",
                "error_code": getattr(exc, "error_code", None),
            }
        }
    logger.error("Unexpected error: %s", exc, exc_info=True)
    return {"result": {"error": f"An unexpected error occurred: {exc}"}}
