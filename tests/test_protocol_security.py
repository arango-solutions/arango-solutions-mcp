"""Protocol-boundary tests for MCP HTTP transport security."""

from __future__ import annotations

import pytest
from mcp.server.transport_security import TransportSecurityMiddleware
from starlette.requests import Request

from arangodb_mcp.server import mcp_app


def _request(*headers: tuple[bytes, bytes]) -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/mcp",
            "raw_path": b"/mcp",
            "query_string": b"",
            "headers": list(headers),
            "server": ("localhost", 8000),
            "client": ("testclient", 12345),
        }
    )


@pytest.mark.asyncio
async def test_invalid_host_is_rejected():
    middleware = TransportSecurityMiddleware(mcp_app.settings.transport_security)
    response = await middleware.validate_request(
        _request((b"host", b"attacker.example"), (b"content-type", b"application/json")),
        is_post=True,
    )

    assert response is not None
    assert response.status_code == 421


@pytest.mark.asyncio
async def test_invalid_browser_origin_is_rejected():
    middleware = TransportSecurityMiddleware(mcp_app.settings.transport_security)
    response = await middleware.validate_request(
        _request(
            (b"host", b"localhost:8000"),
            (b"origin", b"https://attacker.example"),
            (b"content-type", b"application/json"),
        ),
        is_post=True,
    )

    assert response is not None
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_allowed_host_and_origin_pass_transport_security():
    middleware = TransportSecurityMiddleware(mcp_app.settings.transport_security)
    response = await middleware.validate_request(
        _request(
            (b"host", b"localhost:8000"),
            (b"origin", b"http://localhost:3000"),
            (b"content-type", b"application/json"),
        ),
        is_post=True,
    )

    assert response is None
