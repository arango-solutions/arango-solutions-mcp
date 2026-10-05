"""Legacy static-bearer and OIDC auth middleware exports for MCP HTTP.

The legacy middleware remains dependency-light and constant-time. Production
OIDC validation is implemented in :mod:`oidc` and re-exported here so HTTP
authentication has one stable integration boundary.
"""

from __future__ import annotations

import hmac
import logging
from typing import Any, Awaitable, Callable, Collection, MutableMapping, Optional

from arangodb_mcp.oidc import OIDCAuthMiddleware
from arangodb_mcp.policy.actor_context import actor_scope

__all__ = ["BearerTokenAuthMiddleware", "OIDCAuthMiddleware"]

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
        actor_id: str = "legacy-http",
        health_app: Optional[Callable[..., Awaitable[None]]] = None,
        health_path: str = "/healthz",
        health_paths: Optional[Collection[str]] = None,
    ) -> None:
        if not expected_token:
            raise ValueError("expected_token must be a non-empty string")
        self._app = app
        # Pre-compute the full expected header value as bytes for hmac.compare_digest.
        self._expected_header = f"Bearer {expected_token}".encode("latin-1")
        self._actor_id = actor_id
        self._health_app = health_app
        self._health_paths = frozenset((health_path,) if health_paths is None else health_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        # Bypass auth for configured probe endpoints. The probe app itself
        # decides what HTTP methods it supports; we only dispatch exact paths.
        if self._health_app is not None and scope.get("path") in self._health_paths:
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

        with actor_scope(self._actor_id):
            await self._app(scope, receive, send)
