"""MCP 2026-07-28 Streamable HTTP request-metadata validation."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Awaitable, Callable
from typing import Any, Literal

ASGIApp = Callable[
    [
        dict[str, Any],
        Callable[[], Awaitable[dict[str, Any]]],
        Callable[[dict[str, Any]], Awaitable[None]],
    ],
    Awaitable[None],
]
ProtocolMode = Literal["strict", "legacy", "auto"]

CURRENT_PROTOCOL_VERSION = "2026-07-28"
_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
_NAMED_METHODS = frozenset({"tools/call", "resources/read", "prompts/get"})
_CACHE_HINTS: dict[str, tuple[int, str]] = {
    "tools/list": (300_000, "public"),
    "prompts/list": (300_000, "public"),
    "resources/list": (60_000, "private"),
    "resources/read": (60_000, "private"),
    "resources/templates/list": (300_000, "public"),
}
_BASE64_PREFIX = "=?base64?"
_BASE64_SUFFIX = "?="


class ProtocolMetadataMiddleware:
    """Validate mirrored MCP routing headers before the SDK reads the body.

    ``auto`` accepts a legacy request only when none of the 2026 routing
    headers are present. Once a client sends any routing header, the complete
    strict contract is enforced so intermediaries never observe unchecked
    metadata.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        mode: ProtocolMode = "auto",
        mcp_path: str = "/mcp",
        supported_versions: tuple[str, ...] = (CURRENT_PROTOCOL_VERSION,),
        max_body_size: int = 4 * 1024 * 1024,
    ) -> None:
        self.app = app
        self.mode = mode
        self.mcp_path = mcp_path
        self.supported_versions = supported_versions
        self.max_body_size = max_body_size

    async def __call__(self, scope, receive, send) -> None:
        if (
            self.mode == "strict"
            and scope.get("type") == "http"
            and scope.get("path") == self.mcp_path
            and scope.get("method") != "POST"
        ):
            await send(
                {
                    "type": "http.response.start",
                    "status": 405,
                    "headers": [(b"allow", b"POST"), (b"content-length", b"0")],
                }
            )
            await send({"type": "http.response.body", "body": b""})
            return

        if (
            self.mode == "legacy"
            or scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != self.mcp_path
        ):
            await self.app(scope, receive, send)
            return

        body = await self._read_body(receive)
        if body is None:
            await self._send_error(send, None, -32600, "Request body exceeds configured limit")
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        routing_headers_present = any(
            name in headers for name in ("mcp-protocol-version", "mcp-method", "mcp-name")
        )
        if self.mode == "auto" and not routing_headers_present:
            await self.app(scope, self._replay(body), send)
            return

        try:
            message = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            await self.app(scope, self._replay(body), send)
            return
        if not isinstance(message, dict):
            await self.app(scope, self._replay(body), send)
            return

        error = self._validate(headers, message)
        if error is not None:
            code, text, data = error
            await self._send_error(send, message.get("id"), code, text, data)
            return

        method = message.get("method")
        cache_hint = _CACHE_HINTS.get(method) if isinstance(method, str) else None
        if cache_hint is None:
            await self.app(scope, self._replay(body), send)
            return
        await self.app(
            scope,
            self._replay(body),
            self._cache_aware_send(send, ttl_ms=cache_hint[0], cache_scope=cache_hint[1]),
        )

    async def _read_body(self, receive) -> bytes | None:
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_body_size:
                return None
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        return b"".join(chunks)

    @staticmethod
    def _replay(body: bytes):
        sent = False

        async def receive() -> dict[str, Any]:
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        return receive

    def _validate(
        self, headers: dict[str, str], message: dict[str, Any]
    ) -> tuple[int, str, dict[str, Any] | None] | None:
        version = headers.get("mcp-protocol-version")
        if not version:
            return -32020, "Header mismatch: MCP-Protocol-Version is required", None
        if version not in self.supported_versions:
            return (
                -32022,
                "Unsupported protocol version",
                {"supported": list(self.supported_versions), "requested": version},
            )

        params = message.get("params")
        params = params if isinstance(params, dict) else {}
        meta = params.get("_meta")
        meta = meta if isinstance(meta, dict) else {}
        if meta.get(_VERSION_META_KEY) != version:
            return (
                -32020,
                "Header mismatch: MCP-Protocol-Version does not match params._meta",
                None,
            )

        body_method = message.get("method")
        header_method = headers.get("mcp-method")
        if not header_method or header_method != body_method:
            return -32020, "Header mismatch: Mcp-Method does not match body method", None

        if body_method in _NAMED_METHODS:
            source_key = "uri" if body_method == "resources/read" else "name"
            body_name = params.get(source_key)
            header_name = headers.get("mcp-name")
            if not isinstance(body_name, str) or header_name is None:
                return -32020, "Header mismatch: Mcp-Name is required", None
            decoded_name = _decode_header_value(header_name)
            if decoded_name is None or decoded_name != body_name:
                return -32020, "Header mismatch: Mcp-Name does not match body value", None

        return None

    @staticmethod
    def _cache_aware_send(send, *, ttl_ms: int, cache_scope: str):
        start_message: dict[str, Any] | None = None
        chunks: list[bytes] = []
        passthrough = False

        async def send_with_cache_metadata(message: dict[str, Any]) -> None:
            nonlocal start_message, passthrough
            if message["type"] == "http.response.start":
                start_message = message
                return
            if passthrough:
                await send(message)
                return
            if message["type"] != "http.response.body" or start_message is None:
                await send(message)
                return

            content_type = next(
                (
                    value
                    for name, value in start_message.get("headers", [])
                    if name.lower() == b"content-type"
                ),
                b"",
            )
            if not content_type.lower().startswith(b"application/json"):
                passthrough = True
                await send(start_message)
                await send(message)
                return

            chunks.append(message.get("body", b""))
            if message.get("more_body", False):
                return

            body = b"".join(chunks)
            try:
                payload = json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = None
            if isinstance(payload, dict) and isinstance(payload.get("result"), dict):
                result = payload["result"]
                result.setdefault("resultType", "complete")
                result.setdefault("ttlMs", ttl_ms)
                result.setdefault("cacheScope", cache_scope)
                body = json.dumps(payload, separators=(",", ":")).encode()

            headers = [
                (name, value)
                for name, value in start_message.get("headers", [])
                if name.lower() != b"content-length"
            ]
            headers.append((b"content-length", str(len(body)).encode()))
            await send({**start_message, "headers": headers})
            await send({"type": "http.response.body", "body": body, "more_body": False})

        return send_with_cache_metadata

    @staticmethod
    async def _send_error(
        send,
        request_id: Any,
        code: int,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": request_id, "error": error},
            separators=(",", ":"),
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})


def _decode_header_value(value: str) -> str | None:
    if not (value.startswith(_BASE64_PREFIX) and value.endswith(_BASE64_SUFFIX)):
        return value
    encoded = value[len(_BASE64_PREFIX) : -len(_BASE64_SUFFIX)]
    try:
        return base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
