"""ASGI Prometheus scrape route."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from arangodb_mcp.observability.metrics import get_registry


class MetricsRouter:
    """Serve one unauthenticated scrape path and delegate all other requests."""

    def __init__(self, app, *, path: str = "/metrics", enabled: bool = True) -> None:
        self.app = app
        self.path = path
        self.enabled = enabled

    async def __call__(self, scope, receive, send) -> None:
        if self.enabled and scope.get("type") == "http" and scope.get("path") == self.path:
            if scope.get("method", "GET") != "GET":
                await send(
                    {
                        "type": "http.response.start",
                        "status": 405,
                        "headers": [(b"allow", b"GET"), (b"content-length", b"0")],
                    }
                )
                await send({"type": "http.response.body", "body": b""})
                return
            body = generate_latest(get_registry())
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", CONTENT_TYPE_LATEST.encode("ascii")),
                        (b"content-length", str(len(body)).encode("ascii")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)
