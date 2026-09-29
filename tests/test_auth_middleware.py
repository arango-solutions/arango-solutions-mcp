"""Unit tests for ``auth_middleware.BearerTokenAuthMiddleware``.

These tests use a tiny in-process ASGI test harness so they do not depend on
ArangoDB, FastMCP, or even Starlette. They cover:

* requests with no Authorization header → 401
* requests with the wrong token → 401
* requests with the correct ``Authorization: Bearer <token>`` → pass through
* lifespan / non-HTTP scopes pass through without auth checks
* only the configured liveness/readiness probe paths bypass auth
* "longer wrong prefix" tokens are still rejected (constant-time compare)
* constructing the middleware with an empty token raises ``ValueError``
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

# Ensure the src package is importable when pytest is invoked from a subdirectory.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from arangodb_mcp.auth_middleware import BearerTokenAuthMiddleware  # noqa: E402
from arangodb_mcp.oidc import (  # noqa: E402
    OIDCAuthMiddleware,
    OIDCConfig,
    OIDCConfigurationError,
    OIDCValidator,
)
from arangodb_mcp.policy.actor_context import get_request_identity  # noqa: E402
from arangodb_mcp.policy.credentials import StaticCredentialProvider  # noqa: E402

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
    app,
    *,
    path: str = "/mcp",
    method: str = "POST",
    headers: list[tuple[bytes, bytes]] | None = None,
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


@pytest.mark.parametrize("path", ["/livez", "/readyz", "/healthz"])
def test_probes_with_no_auth_header_dispatch_to_health_app(path):
    """Configured probe paths skip bearer auth."""
    inner = _RecordingApp()
    health = _RecordingHealthApp()
    mw = BearerTokenAuthMiddleware(
        inner,
        TOKEN,
        health_app=health,
        health_paths={"/livez", "/readyz", "/healthz"},
    )

    response = asyncio.run(_send_http_request(mw, path=path, method="GET"))

    assert response["status"] == 200
    assert response["body"] == b'{"status":"ok"}'
    assert len(health.calls) == 1
    assert health.calls[0]["path"] == path
    assert health.calls[0]["method"] == "GET"
    assert inner.http_calls == [], "wrapped MCP app must NOT see probe requests"


def test_probe_without_health_app_still_requires_auth():
    """When no ``health_app`` is configured, ``/readyz`` is just another
    path and must satisfy the bearer-auth check like everything else.
    """
    inner = _RecordingApp()
    mw = BearerTokenAuthMiddleware(inner, TOKEN)

    response = asyncio.run(_send_http_request(mw, path="/readyz", method="GET"))

    assert response["status"] == 401
    assert inner.http_calls == []


def test_probe_post_still_dispatched_to_health_app():
    """The middleware dispatches solely on path; the health app itself
    decides what to do with the wrong method (typically a 405).
    """
    inner = _RecordingApp()
    health = _RecordingHealthApp()
    mw = BearerTokenAuthMiddleware(
        inner,
        TOKEN,
        health_app=health,
        health_paths={"/livez", "/readyz", "/healthz"},
    )

    response = asyncio.run(_send_http_request(mw, path="/readyz", method="POST"))

    # Our recording health app always returns 200; what matters is that the
    # request reached the health app rather than being rejected by auth.
    assert response["status"] == 200
    assert len(health.calls) == 1
    assert health.calls[0]["method"] == "POST"
    assert inner.http_calls == []


def test_custom_health_paths_are_exact():
    """Configured paths are exact; similar or default paths still hit auth."""
    inner = _RecordingApp()
    health = _RecordingHealthApp()
    mw = BearerTokenAuthMiddleware(
        inner,
        TOKEN,
        health_app=health,
        health_paths={"/_/live", "/_/ready"},
    )

    ok = asyncio.run(_send_http_request(mw, path="/_/ready", method="GET"))
    assert ok["status"] == 200
    assert len(health.calls) == 1

    for path in ("/healthz", "/_/ready/"):
        blocked = asyncio.run(_send_http_request(mw, path=path, method="GET"))
        assert blocked["status"] == 401


def _oidc_key(kid: str):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwk.update({"kid": kid, "alg": "RS256", "use": "sig"})
    return private, jwk


def test_oidc_http_escape_hatch_is_explicit_and_constrained():
    kwargs = {
        "issuer": "http://reference-idp:8080",
        "audience": "arangodb-mcp",
        "resource": "http://arangodb-mcp:8000/mcp",
    }
    with pytest.raises(OIDCConfigurationError, match="must use HTTPS"):
        OIDCConfig(**kwargs)

    allowed = OIDCConfig(**kwargs, allow_insecure_http=True)
    assert allowed.allow_insecure_http is True

    with pytest.raises(OIDCConfigurationError, match="must use HTTPS"):
        OIDCConfig(
            issuer="http://issuer.example.com",
            audience="arangodb-mcp",
            resource="http://mcp.example.com/mcp",
            allow_insecure_http=True,
        )


def _access_token(
    private,
    kid: str,
    *,
    issuer: str = "https://issuer.example",
    audience: str = "arangodb-mcp",
    expires_in: int = 300,
    not_before: int | None = None,
    actor: str = "alice",
    scope: str = "mcp:read",
    databases: list[str] | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = int(time.time())
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": actor,
        "exp": now + expires_in,
        "iat": now,
        "scope": scope,
        "arangodb_databases": databases or ["tenant_a"],
    }
    if not_before is not None:
        claims["nbf"] = now + not_before
    claims.update(extra_claims or {})
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": kid})


def _validator(private, jwk, *, handler=None):
    issuer = "https://issuer.example"

    def default_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(
                200,
                json={"issuer": issuer, "jwks_uri": f"{issuer}/jwks"},
            )
        return httpx.Response(200, json={"keys": [jwk]}, headers={"cache-control": "max-age=60"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler or default_handler))
    provider = StaticCredentialProvider.from_json(
        json.dumps(
            {
                "alice": {
                    "username": "alice-db",
                    "password": "server-secret",
                    "databases": ["tenant_a", "tenant_b"],
                }
            }
        )
    )
    return OIDCValidator(
        OIDCConfig(
            issuer=issuer,
            audience="arangodb-mcp",
            resource="https://mcp.example/mcp",
            clock_skew_seconds=0,
        ),
        provider,
        client=client,
    )


@pytest.mark.asyncio
async def test_oidc_validates_signature_issuer_audience_expiry_nbf_and_claims():
    private, jwk = _oidc_key("key-1")
    validator = _validator(private, jwk)

    identity = await validator.validate(
        _access_token(
            private,
            "key-1",
            scope="mcp:read catalog:database",
            databases=["tenant_a", "token-only"],
            extra_claims={"username": "attacker", "password": "token-secret"},
        )
    )

    assert identity.actor_id == "alice"
    assert identity.oauth_scopes == {"mcp:read", "catalog:database"}
    assert identity.databases == {"tenant_a"}
    assert identity.credentials.username == "alice-db"
    assert identity.credentials.password == "server-secret"

    invalid_tokens = [
        _access_token(private, "key-1", issuer="https://wrong.example"),
        _access_token(private, "key-1", audience="wrong-audience"),
        _access_token(private, "key-1", expires_in=-1),
        _access_token(private, "key-1", not_before=120),
    ]
    for token in invalid_tokens:
        with pytest.raises(PermissionError):
            await validator.validate(token)


@pytest.mark.asyncio
async def test_oidc_refreshes_jwks_once_for_rotated_unknown_kid():
    first_private, first_jwk = _oidc_key("key-1")
    second_private, second_jwk = _oidc_key("key-2")
    jwks_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal jwks_requests
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": "https://issuer.example",
                    "jwks_uri": "https://issuer.example/jwks",
                },
            )
        jwks_requests += 1
        keys = [first_jwk] if jwks_requests == 1 else [first_jwk, second_jwk]
        return httpx.Response(200, json={"keys": keys}, headers={"cache-control": "max-age=60"})

    validator = _validator(first_private, first_jwk, handler=handler)
    await validator.validate(_access_token(first_private, "key-1"))
    rotated = await validator.validate(_access_token(second_private, "key-2"))

    assert rotated.actor_id == "alice"
    assert jwks_requests == 2


@pytest.mark.asyncio
async def test_oidc_discovery_failure_is_structured_and_fails_closed():
    private, jwk = _oidc_key("key-1")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    validator = _validator(private, jwk, handler=handler)
    inner = _RecordingApp()
    middleware = OIDCAuthMiddleware(inner, validator)
    response = await _send_http_request(
        middleware,
        headers=[(b"authorization", f"Bearer {_access_token(private, 'key-1')}".encode())],
    )

    assert response["status"] == 503
    assert json.loads(response["body"])["error_code"] == "temporarily_unavailable"
    assert inner.http_calls == []


@pytest.mark.asyncio
async def test_oidc_request_identity_is_reset_after_request():
    private, jwk = _oidc_key("key-1")
    validator = _validator(private, jwk)
    seen = []

    async def inner(scope, receive, send):
        seen.append(get_request_identity())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = OIDCAuthMiddleware(inner, validator)
    response = await _send_http_request(
        middleware,
        headers=[(b"authorization", f"Bearer {_access_token(private, 'key-1')}".encode())],
    )

    assert response["status"] == 200
    assert seen[0].actor_id == "alice"
    assert get_request_identity() is None
