"""Minimal reference OIDC server with an ephemeral process-local RSA key."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = os.environ.get("OIDC_ISSUER", "http://reference-idp:8080").rstrip("/")
AUDIENCE = os.environ.get("OIDC_AUDIENCE", "arangodb-mcp")
ACTOR = os.environ.get("OIDC_ACTOR", "phase4-actor")
DATABASE = os.environ.get("OIDC_DATABASE", "_system")
PORT = int(os.environ.get("PORT", "8080"))

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_KID = f"runtime-{uuid.uuid4().hex}"
_PUBLIC_JWK = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_PRIVATE_KEY.public_key()))
_PUBLIC_JWK.update({"kid": _KID, "alg": "RS256", "use": "sig"})
_COUNTS = {"discovery": 0, "jwks": 0, "token": 0}
_LOCK = threading.Lock()


def _token() -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": ACTOR,
            "iat": now,
            "nbf": now - 1,
            "exp": now + 300,
            "scope": "mcp:read",
            "arangodb_databases": [DATABASE],
        },
        _PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": _KID},
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "ReferenceOIDC/1.0"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._json(200, {"status": "ok"})
            return
        if self.path == "/.well-known/openid-configuration":
            self._count("discovery")
            self._json(
                200,
                {
                    "issuer": ISSUER,
                    "jwks_uri": f"{ISSUER}/jwks",
                    "id_token_signing_alg_values_supported": ["RS256"],
                    "token_endpoint": f"{ISSUER}/token",
                },
                cache_control="public, max-age=30",
            )
            return
        if self.path == "/jwks":
            self._count("jwks")
            self._json(
                200,
                {"keys": [_PUBLIC_JWK]},
                cache_control="public, max-age=30",
            )
            return
        if self.path == "/token":
            self._count("token")
            self._json(
                200,
                {
                    "access_token": _token(),
                    "token_type": "Bearer",
                    "expires_in": 300,
                },
                cache_control="no-store",
            )
            return
        if self.path == "/stats":
            with _LOCK:
                counts = dict(_COUNTS)
            self._json(200, counts, cache_control="no-store")
            return
        self._json(404, {"error": "not_found"})

    def log_message(self, format: str, *args: Any) -> None:
        # Paths and statuses are useful; authorization material is never logged.
        print(f"reference-idp {self.address_string()} {format % args}", flush=True)

    @staticmethod
    def _count(name: str) -> None:
        with _LOCK:
            _COUNTS[name] += 1

    def _json(
        self,
        status: int,
        body: dict[str, Any],
        *,
        cache_control: str = "no-store",
    ) -> None:
        payload = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", cache_control)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    print(f"reference-idp ready issuer={ISSUER} kid={_KID}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
