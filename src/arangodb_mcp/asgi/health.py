"""Unauthenticated process-liveness and dependency-readiness endpoints."""

from __future__ import annotations

import asyncio
import json

from arangodb_mcp.arango_connector import arango_connector

PROBE_PATHS = frozenset({"/livez", "/readyz", "/healthz"})


async def health_app(scope, receive, send):
    """Serve exact-path, GET-only liveness and readiness probes."""
    path = scope.get("path")
    response_headers = [
        (b"content-type", b"application/json"),
        (b"cache-control", b"no-store"),
    ]

    if path == "/healthz":
        response_headers.extend(
            [
                (b"deprecation", b"@1785888000"),
                (b"link", b'</readyz>; rel="successor-version"'),
            ]
        )

    if scope.get("method") != "GET":
        await send(
            {
                "type": "http.response.start",
                "status": 405,
                "headers": [*response_headers, (b"allow", b"GET")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"error":"method not allowed"}'})
        return

    if path == "/livez":
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": response_headers,
            }
        )
        await send({"type": "http.response.body", "body": b'{"status":"alive"}'})
        return

    if path not in {"/readyz", "/healthz"}:
        await send(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": response_headers,
            }
        )
        await send({"type": "http.response.body", "body": b'{"error":"not found"}'})
        return

    healthy = await asyncio.to_thread(arango_connector.health_check)
    if healthy:
        body = json.dumps(
            {
                "status": "ready",
                "checks": {"arangodb": "ok"},
                "server_version": arango_connector.server_version,
            }
        ).encode()
        status = 200
    else:
        body = b'{"status":"not_ready","checks":{"arangodb":"unhealthy"}}'
        status = 503

    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": response_headers,
        }
    )
    await send({"type": "http.response.body", "body": body})


class ProbeRouter:
    """Route public health probes without widening the MCP auth bypass."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") == "http" and scope.get("path") in PROBE_PATHS:
            await health_app(scope, receive, send)
            return
        await self.app(scope, receive, send)
