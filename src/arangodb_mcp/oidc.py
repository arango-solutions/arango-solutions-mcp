"""Provider-neutral OIDC resource-server validation and RFC 9728 metadata."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, MutableMapping
from urllib.parse import urlsplit

import httpx
import jwt

from arangodb_mcp.policy.actor_context import RequestIdentity, identity_scope
from arangodb_mcp.policy.credentials import CredentialResolutionError, StaticCredentialProvider

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

OPERATION_SCOPES = frozenset({"mcp:read", "mcp:write", "mcp:admin"})


class OIDCConfigurationError(ValueError):
    """Raised when OIDC cannot be configured safely."""


class OIDCValidationError(PermissionError):
    """A stable, non-sensitive access-token rejection."""

    def __init__(self, code: str, description: str) -> None:
        super().__init__(description)
        self.code = code
        self.description = description


@dataclass(frozen=True)
class OIDCConfig:
    issuer: str
    audience: str
    resource: str
    algorithms: tuple[str, ...] = ("RS256",)
    actor_claim: str = "sub"
    database_claim: str = "arangodb_databases"
    clock_skew_seconds: int = 30
    cache_ttl_seconds: int = 300
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        if not self.issuer or not self.audience or not self.resource:
            raise OIDCConfigurationError("OIDC issuer, audience, and resource must be configured")
        if not _secure_http_url(
            self.issuer, allow_insecure_http=self.allow_insecure_http
        ) or not _secure_http_url(self.resource, allow_insecure_http=self.allow_insecure_http):
            raise OIDCConfigurationError(
                "OIDC issuer and resource must use HTTPS; constrained HTTP is available only "
                "when the test/development escape hatch is explicitly enabled"
            )
        if not self.algorithms or any(algorithm.startswith("HS") for algorithm in self.algorithms):
            raise OIDCConfigurationError("OIDC algorithms must be asymmetric signing algorithms")
        if self.clock_skew_seconds < 0 or self.cache_ttl_seconds <= 0:
            raise OIDCConfigurationError("OIDC clock skew and cache TTL must be positive")


class OIDCValidator:
    """Validate JWT access tokens using discovery and a refreshable JWKS cache."""

    def __init__(
        self,
        config: OIDCConfig,
        credentials: StaticCredentialProvider,
        *,
        client: httpx.AsyncClient | None = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.config = config
        self.credentials = credentials
        self._client = client or httpx.AsyncClient(timeout=5.0, follow_redirects=False)
        self._owns_client = client is None
        self._now = now
        self._jwks_uri: str | None = None
        self._keys: dict[str, dict[str, Any]] = {}
        self._expires_at = 0.0
        self._refresh_lock = asyncio.Lock()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def validate(self, token: str) -> RequestIdentity:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise OIDCValidationError("invalid_token", "Access token is malformed") from exc

        algorithm = header.get("alg")
        key_id = header.get("kid")
        if algorithm not in self.config.algorithms or not isinstance(key_id, str) or not key_id:
            raise OIDCValidationError(
                "invalid_token", "Access token uses an unsupported signing key"
            )

        key_data = await self._get_key(key_id)
        try:
            signing_key = jwt.PyJWK.from_dict(key_data, algorithm=algorithm).key
            claims = jwt.decode(
                token,
                key=signing_key,
                algorithms=list(self.config.algorithms),
                audience=self.config.audience,
                issuer=self.config.issuer,
                leeway=self.config.clock_skew_seconds,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise OIDCValidationError("invalid_token", "Access token has expired") from exc
        except jwt.ImmatureSignatureError as exc:
            raise OIDCValidationError("invalid_token", "Access token is not yet valid") from exc
        except jwt.InvalidAudienceError as exc:
            raise OIDCValidationError("invalid_token", "Access token audience is invalid") from exc
        except jwt.InvalidIssuerError as exc:
            raise OIDCValidationError("invalid_token", "Access token issuer is invalid") from exc
        except jwt.PyJWTError as exc:
            raise OIDCValidationError("invalid_token", "Access token validation failed") from exc

        actor = claims.get(self.config.actor_claim)
        subject = claims.get("sub")
        if not isinstance(actor, str) or not actor or not isinstance(subject, str) or not subject:
            raise OIDCValidationError("invalid_token", "Access token has no usable actor identity")
        oauth_scopes = _parse_scopes(claims.get("scope"))
        token_databases = _parse_databases(claims.get(self.config.database_claim))
        try:
            credentials = self.credentials.resolve(actor)
        except CredentialResolutionError as exc:
            raise OIDCValidationError(
                "insufficient_authorization",
                "No database authority is configured for this actor",
            ) from exc
        databases = token_databases & credentials.databases
        if not databases:
            raise OIDCValidationError(
                "insufficient_authorization",
                "Token and credential database authority do not overlap",
            )
        return RequestIdentity(
            actor_id=actor,
            issuer=self.config.issuer,
            subject=subject,
            oauth_scopes=oauth_scopes,
            databases=databases,
            credentials=credentials,
        )

    async def _get_key(self, key_id: str) -> dict[str, Any]:
        if self._now() >= self._expires_at:
            await self._refresh()
        key = self._keys.get(key_id)
        if key is None:
            # A previously unknown kid is the normal signal for signing-key rotation.
            await self._refresh(force=True)
            key = self._keys.get(key_id)
        if key is None:
            raise OIDCValidationError("invalid_token", "Access token signing key is unknown")
        return key

    async def _refresh(self, *, force: bool = False) -> None:
        async with self._refresh_lock:
            if not force and self._keys and self._now() < self._expires_at:
                return
            try:
                if self._jwks_uri is None:
                    discovery_url = (
                        f"{self.config.issuer.rstrip('/')}/.well-known/openid-configuration"
                    )
                    response = await self._client.get(discovery_url)
                    response.raise_for_status()
                    discovery = response.json()
                    if discovery.get("issuer") != self.config.issuer:
                        raise OIDCConfigurationError(
                            "OIDC discovery issuer does not match configured issuer"
                        )
                    jwks_uri = discovery.get("jwks_uri")
                    if not isinstance(jwks_uri, str) or not _secure_http_url(
                        jwks_uri,
                        allow_insecure_http=self.config.allow_insecure_http,
                    ):
                        raise OIDCConfigurationError("OIDC discovery returned an invalid jwks_uri")
                    self._jwks_uri = jwks_uri

                response = await self._client.get(self._jwks_uri)
                response.raise_for_status()
                document = response.json()
                keys = document.get("keys")
                if not isinstance(keys, list):
                    raise OIDCConfigurationError("OIDC JWKS response has no keys array")
                parsed = {
                    key["kid"]: key
                    for key in keys
                    if isinstance(key, dict)
                    and isinstance(key.get("kid"), str)
                    and key.get("kty") in {"RSA", "EC", "OKP"}
                }
                if not parsed:
                    raise OIDCConfigurationError("OIDC JWKS response has no usable signing keys")
                self._keys = parsed
                self._expires_at = self._now() + _cache_ttl(
                    response.headers.get("cache-control"), self.config.cache_ttl_seconds
                )
            except (OIDCConfigurationError, httpx.HTTPError, ValueError, TypeError) as exc:
                raise OIDCValidationError(
                    "temporarily_unavailable", "Authorization server metadata is unavailable"
                ) from exc


class OIDCAuthMiddleware:
    """Authenticate HTTP MCP requests and bind isolated request identity."""

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        validator: OIDCValidator,
        *,
        public_app: Callable[..., Awaitable[None]] | None = None,
        public_paths: frozenset[str] = frozenset(),
    ) -> None:
        self._app = app
        self._validator = validator
        self._public_app = public_app
        self._public_paths = public_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            try:
                await self._app(scope, receive, send)
            finally:
                if scope.get("type") == "lifespan":
                    await self._validator.close()
            return
        if self._public_app is not None and scope.get("path") in self._public_paths:
            await self._public_app(scope, receive, send)
            return

        authorization = _header(scope, b"authorization")
        if authorization is None or not authorization.startswith("Bearer "):
            await _send_auth_error(
                send, OIDCValidationError("invalid_token", "Bearer token required")
            )
            return
        token = authorization[7:]
        if not token:
            await _send_auth_error(
                send, OIDCValidationError("invalid_token", "Bearer token required")
            )
            return
        try:
            identity = await self._validator.validate(token)
        except OIDCValidationError as exc:
            await _send_auth_error(send, exc)
            return
        with identity_scope(identity):
            await self._app(scope, receive, send)


class ProtectedResourceRouter:
    """Serve public probes and RFC 9728 metadata before MCP authentication."""

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        *,
        config: OIDCConfig,
        probe_app: Callable[..., Awaitable[None]],
        probe_paths: frozenset[str],
    ) -> None:
        self._app = app
        self._probe_app = probe_app
        self._probe_paths = probe_paths
        resource_path = urlsplit(config.resource).path.rstrip("/")
        self.metadata_paths = frozenset(
            {
                "/.well-known/oauth-protected-resource",
                f"/.well-known/oauth-protected-resource{resource_path}",
            }
        )
        self.public_paths = self.metadata_paths | probe_paths
        self._metadata = json.dumps(
            {
                "resource": config.resource,
                "authorization_servers": [config.issuer],
                "bearer_methods_supported": ["header"],
                "scopes_supported": sorted(OPERATION_SCOPES),
            },
            separators=(",", ":"),
        ).encode("utf-8")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "http":
            path = scope.get("path")
            if path in self._probe_paths:
                await self._probe_app(scope, receive, send)
                return
            if path in self.metadata_paths:
                if scope.get("method") != "GET":
                    await _send_json(send, 405, {"error": "method_not_allowed"})
                    return
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"cache-control", b"public, max-age=300"),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": self._metadata})
                return
        await self._app(scope, receive, send)


def _parse_scopes(raw: Any) -> frozenset[str]:
    if not isinstance(raw, str):
        raise OIDCValidationError("invalid_token", "Access token scope claim must be a string")
    return frozenset(item for item in raw.split() if item)


def _parse_databases(raw: Any) -> frozenset[str]:
    if (
        not isinstance(raw, list)
        or not raw
        or not all(isinstance(item, str) and item for item in raw)
    ):
        raise OIDCValidationError(
            "invalid_token", "Access token database allowlist claim is invalid"
        )
    return frozenset(raw)


def _cache_ttl(cache_control: str | None, default: int) -> int:
    if cache_control:
        for directive in cache_control.split(","):
            name, separator, value = directive.strip().partition("=")
            if name.lower() == "max-age" and separator and value.isdigit():
                return max(1, min(int(value), 3600))
    return default


def _secure_http_url(value: str, *, allow_insecure_http: bool = False) -> bool:
    parsed = urlsplit(value)
    if not parsed.netloc or parsed.fragment:
        return False
    if parsed.scheme == "https":
        return True
    if parsed.scheme != "http" or not allow_insecure_http or parsed.hostname is None:
        return False
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "::1"} or hostname.endswith((".test", ".local")):
        return True
    try:
        return ipaddress.ip_address(hostname).is_private
    except ValueError:
        # Docker Compose service discovery uses single-label DNS names.
        return "." not in hostname


def _header(scope: Scope, name: bytes) -> str | None:
    for header_name, value in scope.get("headers", []):
        if header_name.lower() == name:
            return value.decode("latin-1")
    return None


async def _send_auth_error(send: Send, error: OIDCValidationError) -> None:
    escaped_description = error.description.replace('"', "'")
    await send(
        {
            "type": "http.response.start",
            "status": 503 if error.code == "temporarily_unavailable" else 401,
            "headers": [
                (b"content-type", b"application/json"),
                (
                    b"www-authenticate",
                    (
                        f'Bearer error="{error.code}", '
                        f'error_description="{escaped_description}"'
                    ).encode("latin-1"),
                ),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": json.dumps(
                {
                    "error": error.code,
                    "error_description": error.description,
                    "error_code": error.code,
                },
                separators=(",", ":"),
            ).encode("utf-8"),
        }
    )


async def _send_json(send: Send, status: int, body: dict[str, Any]) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": json.dumps(body, separators=(",", ":")).encode("utf-8"),
        }
    )
