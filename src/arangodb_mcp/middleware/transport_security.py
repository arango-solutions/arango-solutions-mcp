"""Outer MCP Host/Origin validation applied before authentication."""

from __future__ import annotations

from mcp.server.transport_security import (
    TransportSecurityMiddleware as SDKTransportSecurityValidator,
)
from starlette.requests import Request


class MCPTransportSecurityMiddleware:
    """Enforce SDK transport checks before any MCP middleware trusts headers."""

    def __init__(self, app, settings, *, mcp_path: str = "/mcp") -> None:
        self.app = app
        self.mcp_path = mcp_path
        self.validator = SDKTransportSecurityValidator(settings)

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") == "http" and scope.get("path") == self.mcp_path:
            response = await self.validator.validate_request(
                Request(scope),
                is_post=scope.get("method") == "POST",
            )
            if response is not None:
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
