"""Unit tests for ``auth_middleware.BearerTokenAuthMiddleware``.

These tests use a tiny in-process ASGI test harness so they do not depend on
ArangoDB, FastMCP, or even Starlette. They cover:

* requests with no Authorization header → 401
* requests with the wrong token → 401
* requests with the correct ``Authorization: Bearer <token>`` → pass through
* lifespan / non-HTTP scopes pass through without auth checks
* "longer wrong prefix" tokens are still rejected (constant-time compare)
* constructing the middleware with an empty token raises ``ValueError``
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

# Ensure the repo root is importable when pytest is invoked from a subdirectory.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from auth_middleware import BearerTokenAuthMiddleware  # noqa: E402

TOKEN = "supersecret-token-1234567890"


# ---------------------------------------------------------------------------
# Tiny ASGI harness
# ---------------------------------------------------------------------------


class _RecordingApp:
    """Minimal ASGI app that records calls and returns a 200 OK for HTTP scopes.

    For ``lifespan`` scopes it answers the standard lifespan protocol so the
    pass-through behaviour can be observed end-to-end.
    """

    def __init__(self) -> None:
        self.http_calls: list[dict[str, Any]] = []
        self.lifespan_started = False
        self.lifespan_shutdown = False

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            self.http_calls.append({"path": scope.get("path"), "method": scope.get("method")})
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"text/plain")],
                }
            )
            await send({"type": "http.response.body", "body": b"ok"})
            return

        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    self.lifespan_started = True
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    self.lifespan_shutdown = True
                    await send({"type": "lifespan.shutdown.complete"})
                    return


async def _send_http_request(
    app, *, path: str = "/mcp", method: str = "POST", headers: list[tuple[bytes, bytes]] | None = None
) -> dict[str, Any]:
    """Drive ``app`` with a synthetic ASGI HTTP request and collect the response."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers or [],
        "server": ("testserver", 80),
        "client": ("testclient", 12345),
    }

    body_sent = asyncio.Event()

    async def receive():
        if body_sent.is_set():
            return {"type": "http.disconnect"}
        body_sent.set()
        return {"type": "http.request", "body": b"", "more_body": False}

    response: dict[str, Any] = {"status": None, "headers": [], "body": b""}

    async def send(message):
        if message["type"] == "http.response.start":
            response["status"] = message["status"]
            response["headers"] = message.get("headers", [])
        elif message["type"] == "http.response.body":
            response["body"] += message.get("body", b"")

    await app(scope, receive, send)
    return response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_construct_with_empty_token_raises():
    inner = _RecordingApp()
    with pytest.raises(ValueError):
        BearerTokenAuthMiddleware(inner, "")


def test_missing_auth_header_returns_401():
    inner = _RecordingApp()
    mw = BearerTokenAuthMiddleware(inner, TOKEN)

    response = asyncio.run(_send_http_request(mw))

    assert response["status"] == 401
    assert b'"unauthorized"' in response["body"]
    # WWW-Authenticate header is set on rejection.
    assert (b"www-authenticate", b'Bearer realm="mcp"') in response["headers"]
    assert inner.http_calls == [], "inner app must NOT be called when auth fails"


def test_wrong_token_returns_401():
    inner = _RecordingApp()
    mw = BearerTokenAuthMiddleware(inner, TOKEN)
    headers = [(b"authorization", b"Bearer not-the-right-token")]

    response = asyncio.run(_send_http_request(mw, headers=headers))

    assert response["status"] == 401
    assert inner.http_calls == []


def test_correct_token_passes_through():
    inner = _RecordingApp()
    mw = BearerTokenAuthMiddleware(inner, TOKEN)
    headers = [(b"authorization", f"Bearer {TOKEN}".encode())]

    response = asyncio.run(_send_http_request(mw, headers=headers))

    assert response["status"] == 200
    assert response["body"] == b"ok"
    assert len(inner.http_calls) == 1
    assert inner.http_calls[0]["path"] == "/mcp"


def test_lifespan_scope_passes_through_without_auth_check():
    inner = _RecordingApp()
    mw = BearerTokenAuthMiddleware(inner, TOKEN)

    async def drive_lifespan() -> None:
        scope = {"type": "lifespan", "asgi": {"version": "3.0"}}
        messages_in: asyncio.Queue = asyncio.Queue()
        await messages_in.put({"type": "lifespan.startup"})
        await messages_in.put({"type": "lifespan.shutdown"})

        async def receive():
            return await messages_in.get()

        sent: list[dict[str, Any]] = []

        async def send(message):
            sent.append(message)

        await mw(scope, receive, send)
        # The recording app should have completed both phases of lifespan.
        assert {"type": "lifespan.startup.complete"} in sent
        assert {"type": "lifespan.shutdown.complete"} in sent

    asyncio.run(drive_lifespan())
    assert inner.lifespan_started is True
    assert inner.lifespan_shutdown is True


def test_websocket_or_other_scope_passes_through():
    """Non-HTTP, non-lifespan scopes (e.g. websocket) are not inspected by this
    middleware. The contract is: only ``http`` is checked."""

    seen: list[str] = []

    async def fake_app(scope, receive, send):
        seen.append(scope["type"])

    mw = BearerTokenAuthMiddleware(fake_app, TOKEN)

    async def drive() -> None:
        await mw({"type": "websocket"}, lambda: asyncio.sleep(0), lambda m: asyncio.sleep(0))

    asyncio.run(drive())
    assert seen == ["websocket"]


def test_longer_wrong_prefix_token_still_rejected():
    """A wrong token whose prefix matches the expected value must still be
    rejected. ``hmac.compare_digest`` should not short-circuit on mismatch.
    """
    inner = _RecordingApp()
    mw = BearerTokenAuthMiddleware(inner, TOKEN)

    bogus = TOKEN + "EXTRA"  # correct prefix, then garbage
    headers = [(b"authorization", f"Bearer {bogus}".encode())]

    response = asyncio.run(_send_http_request(mw, headers=headers))

    assert response["status"] == 401
    assert inner.http_calls == []


def test_authorization_with_wrong_scheme_rejected():
    """``Basic <creds>`` (or anything not equal to the full expected header)
    must be rejected even if the credential portion happens to match."""
    inner = _RecordingApp()
    mw = BearerTokenAuthMiddleware(inner, TOKEN)
    headers = [(b"authorization", f"Basic {TOKEN}".encode())]

    response = asyncio.run(_send_http_request(mw, headers=headers))

    assert response["status"] == 401
    assert inner.http_calls == []


# ---------------------------------------------------------------------------
# Health-bypass tests
# ---------------------------------------------------------------------------


class _RecordingHealthApp:
    """ASGI app that records calls and returns a fixed 200 ``{"status":"ok"}``."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, scope, receive, send):
        self.calls.append({"path": scope.get("path"), "method": scope.get("method")})
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"status":"ok"}'})


def test_healthz_with_no_auth_header_dispatches_to_health_app():
    """When ``health_app`` is set, ``GET /healthz`` skips the bearer check
    and is dispatched to the health app even with no Authorization header.
    """
    inner = _RecordingApp()
    health = _RecordingHealthApp()
    mw = BearerTokenAuthMiddleware(inner, TOKEN, health_app=health)

    response = asyncio.run(_send_http_request(mw, path="/healthz", method="GET"))

    assert response["status"] == 200
    assert response["body"] == b'{"status":"ok"}'
    assert len(health.calls) == 1
    assert health.calls[0]["path"] == "/healthz"
    assert health.calls[0]["method"] == "GET"
    assert inner.http_calls == [], "wrapped MCP app must NOT see /healthz"


def test_healthz_without_health_app_still_requires_auth():
    """When no ``health_app`` is configured, ``/healthz`` is just another
    path and must satisfy the bearer-auth check like everything else.
    """
    inner = _RecordingApp()
    mw = BearerTokenAuthMiddleware(inner, TOKEN)

    response = asyncio.run(_send_http_request(mw, path="/healthz", method="GET"))

    assert response["status"] == 401
    assert inner.http_calls == []


def test_healthz_post_still_dispatched_to_health_app():
    """The middleware dispatches solely on path; the health app itself
    decides what to do with the wrong method (typically a 405).
    """
    inner = _RecordingApp()
    health = _RecordingHealthApp()
    mw = BearerTokenAuthMiddleware(inner, TOKEN, health_app=health)

    response = asyncio.run(_send_http_request(mw, path="/healthz", method="POST"))

    # Our recording health app always returns 200; what matters is that the
    # request reached the health app rather than being rejected by auth.
    assert response["status"] == 200
    assert len(health.calls) == 1
    assert health.calls[0]["method"] == "POST"
    assert inner.http_calls == []


def test_custom_health_path():
    """The ``health_path`` is configurable; other paths still hit auth."""
    inner = _RecordingApp()
    health = _RecordingHealthApp()
    mw = BearerTokenAuthMiddleware(
        inner, TOKEN, health_app=health, health_path="/_/ready"
    )

    ok = asyncio.run(_send_http_request(mw, path="/_/ready", method="GET"))
    assert ok["status"] == 200
    assert len(health.calls) == 1

    blocked = asyncio.run(_send_http_request(mw, path="/healthz", method="GET"))
    assert blocked["status"] == 401, (
        "default /healthz should not bypass auth when health_path was overridden"
    )
