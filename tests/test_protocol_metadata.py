"""MCP 2026-07-28 mirrored-header compatibility tests."""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from arangodb_mcp.middleware.protocol import ProtocolMetadataMiddleware


class _RecordingApp:
    def __init__(self) -> None:
        self.body: dict[str, Any] | None = None

    async def __call__(self, scope, receive, send) -> None:
        message = await receive()
        self.body = json.loads(message["body"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


async def _request(
    middleware: ProtocolMetadataMiddleware,
    body: dict[str, Any],
    *headers: tuple[bytes, bytes],
    method: str = "POST",
) -> dict[str, Any]:
    scope = {
        "type": "http",
        "method": method,
        "path": "/mcp",
        "headers": [(b"content-type", b"application/json"), *headers],
    }
    request_sent = False

    async def receive():
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": json.dumps(body).encode(), "more_body": False}

    response: dict[str, Any] = {"status": None, "body": b""}

    async def send(message):
        if message["type"] == "http.response.start":
            response["status"] = message["status"]
        elif message["type"] == "http.response.body":
            response["body"] += message.get("body", b"")

    await middleware(scope, receive, send)
    return response


def _tool_call(name: str = "list-collections") -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": {},
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        },
    }


def _strict_headers(name: str = "list-collections") -> tuple[tuple[bytes, bytes], ...]:
    return (
        (b"mcp-protocol-version", b"2026-07-28"),
        (b"mcp-method", b"tools/call"),
        (b"mcp-name", name.encode()),
    )


@pytest.mark.asyncio
async def test_auto_mode_replays_headerless_legacy_request():
    app = _RecordingApp()
    response = await _request(ProtocolMetadataMiddleware(app), _tool_call())

    assert response["status"] == 200
    assert app.body == _tool_call()


@pytest.mark.asyncio
async def test_strict_mode_requires_routing_headers():
    response = await _request(
        ProtocolMetadataMiddleware(_RecordingApp(), mode="strict"), _tool_call()
    )

    assert response["status"] == 400
    payload = json.loads(response["body"])
    assert payload["error"]["code"] == -32020


@pytest.mark.asyncio
async def test_strict_mode_removes_legacy_get_endpoint():
    response = await _request(
        ProtocolMetadataMiddleware(_RecordingApp(), mode="strict"),
        _tool_call(),
        method="GET",
    )

    assert response["status"] == 405


@pytest.mark.asyncio
async def test_matching_routing_headers_pass_and_preserve_body():
    app = _RecordingApp()
    body = _tool_call()
    response = await _request(
        ProtocolMetadataMiddleware(app, mode="strict"), body, *_strict_headers()
    )

    assert response["status"] == 200
    assert app.body == body


@pytest.mark.asyncio
async def test_name_mismatch_is_rejected():
    response = await _request(
        ProtocolMetadataMiddleware(_RecordingApp(), mode="strict"),
        _tool_call(),
        *_strict_headers("delete-database"),
    )

    assert response["status"] == 400
    payload = json.loads(response["body"])
    assert payload["error"]["code"] == -32020
    assert payload["id"] == 7


@pytest.mark.asyncio
async def test_base64_sentinel_name_is_decoded_before_comparison():
    name = "manual://AQL reference"
    encoded = base64.b64encode(name.encode()).decode()
    headers = (
        (b"mcp-protocol-version", b"2026-07-28"),
        (b"mcp-method", b"resources/read"),
        (b"mcp-name", f"=?base64?{encoded}?=".encode()),
    )
    body = _tool_call()
    body["method"] = "resources/read"
    body["params"] = {
        "uri": name,
        "_meta": body["params"]["_meta"],
    }

    response = await _request(
        ProtocolMetadataMiddleware(_RecordingApp(), mode="strict"), body, *headers
    )

    assert response["status"] == 200


@pytest.mark.asyncio
async def test_unsupported_version_lists_supported_versions():
    body = _tool_call()
    body["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] = "1900-01-01"
    headers = (
        (b"mcp-protocol-version", b"1900-01-01"),
        (b"mcp-method", b"tools/call"),
        (b"mcp-name", b"list-collections"),
    )

    response = await _request(
        ProtocolMetadataMiddleware(_RecordingApp(), mode="strict"), body, *headers
    )

    assert response["status"] == 400
    payload = json.loads(response["body"])
    assert payload["error"]["code"] == -32022
    assert payload["error"]["data"] == {
        "supported": ["2026-07-28"],
        "requested": "1900-01-01",
    }
