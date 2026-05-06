"""Bearer-token auth middleware for FastMCP HTTP / SSE transports.

This module provides a small ASGI middleware that protects HTTP requests with a
shared bearer token. It is intentionally dependency-free (stdlib only) and uses
constant-time comparison for the token check to avoid trivial timing
side-channels.
"""

from __future__ import annotations

import hmac
import logging
from typing import Any, Awaitable, Callable, MutableMapping, Optional

logger = logging.getLogger(__name__)

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


class BearerTokenAuthMiddleware:
    """Reject HTTP requests lacking a valid ``Authorization: Bearer <token>`` header.

    Wraps a Starlette/FastAPI ASGI application. Only ``http`` scopes are
    inspected; ``lifespan`` and any other scope types pass through unmodified
    so the wrapped app's startup / shutdown hooks (e.g. the ArangoDB
    connection lifespan) continue to run.
    """

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        expected_token: str,
        *,
        health_app: Optional[Callable[..., Awaitable[None]]] = None,
        health_path: str = "/healthz",
    ) -> None:
        if not expected_token:
            raise ValueError("expected_token must be a non-empty string")
        self._app = app
        # Pre-compute the full expected header value as bytes for hmac.compare_digest.
        self._expected_header = f"Bearer {expected_token}".encode("latin-1")
        self._health_app = health_app
        self._health_path = health_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        # Bypass auth for the health endpoint when one is configured. The
        # health app itself decides what HTTP methods it supports; we simply
        # dispatch when the path matches.
        if self._health_app is not None and scope.get("path") == self._health_path:
            await self._health_app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        auth_value = headers.get(b"authorization", b"")

        if not hmac.compare_digest(auth_value, self._expected_header):
            logger.warning(
                "BearerTokenAuthMiddleware: rejecting %s %s — missing or invalid auth header",
                scope.get("method"),
                scope.get("path"),
            )
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"www-authenticate", b'Bearer realm="mcp"'),
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error":"unauthorized"}',
                }
            )
            return

        await self._app(scope, receive, send)
