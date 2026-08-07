"""Composable ASGI application factory for MCP HTTP transports."""

from __future__ import annotations

import logging

from arangodb_mcp.auth_middleware import BearerTokenAuthMiddleware, OIDCAuthMiddleware
from arangodb_mcp.config import settings
from arangodb_mcp.middleware.protocol import ProtocolMetadataMiddleware
from arangodb_mcp.middleware.request_context import RequestContextMiddleware
from arangodb_mcp.middleware.transport_security import MCPTransportSecurityMiddleware
from arangodb_mcp.observability.http import MetricsRouter
from arangodb_mcp.oidc import OIDCConfig, OIDCValidator, ProtectedResourceRouter
from arangodb_mcp.policy.credentials import StaticCredentialProvider
from arangodb_mcp.server import mcp_app

from .health import PROBE_PATHS, ProbeRouter, health_app

logger = logging.getLogger(__name__)


def oidc_config_from_settings() -> OIDCConfig:
    """Build a validated OIDC configuration from environment-backed settings."""
    identity = settings.identity
    algorithms = tuple(
        item.strip() for item in identity.mcp_oidc_algorithms.split(",") if item.strip()
    )
    return OIDCConfig(
        issuer=identity.mcp_oidc_issuer.rstrip("/"),
        audience=identity.mcp_oidc_audience,
        resource=identity.mcp_resource_url,
        algorithms=algorithms,
        actor_claim=identity.mcp_oidc_actor_claim,
        database_claim=identity.mcp_oidc_database_claim,
        clock_skew_seconds=identity.mcp_oidc_clock_skew_seconds,
        cache_ttl_seconds=identity.mcp_oidc_cache_ttl_seconds,
        allow_insecure_http=identity.mcp_oidc_allow_insecure_http,
    )


def oidc_validator_from_settings() -> OIDCValidator:
    """Create the resource-server validator and trusted credential provider."""
    config, provider = validate_oidc_settings()
    return OIDCValidator(config, provider)


def validate_oidc_settings() -> tuple[OIDCConfig, StaticCredentialProvider]:
    """Fail startup on incomplete OIDC or credential-provider configuration."""
    secret = settings.identity.mcp_arango_credentials_json
    if secret is None or not secret.get_secret_value():
        raise ValueError("MCP_ARANGO_CREDENTIALS_JSON is required when OIDC is enabled")
    provider = StaticCredentialProvider.from_json(secret.get_secret_value())
    config = oidc_config_from_settings()
    if config.allow_insecure_http:
        logger.warning(
            "MCP_OIDC_ALLOW_INSECURE_HTTP is ENABLED. This constrained escape hatch is "
            "for isolated test/development networks only."
        )
    return config, provider


def create_http_app(
    transport: str,
    plain_token: str,
    *,
    oidc_validator: OIDCValidator | None = None,
):
    """Compose transport, protocol, auth, probe, and request-context layers."""
    if plain_token and settings.identity.mcp_oidc_issuer:
        raise ValueError("Legacy bearer and OIDC authentication cannot both be enabled")
    if transport == "streamable-http":
        app = mcp_app.streamable_http_app()
        app = ProtocolMetadataMiddleware(
            app,
            mode=settings.server.mcp_protocol_mode,
            mcp_path=mcp_app.settings.streamable_http_path,
            max_body_size=mcp_app.settings.max_request_body_size,
        )
    elif transport == "sse":
        app = mcp_app.sse_app()
    else:
        raise ValueError(f"Unsupported HTTP transport: {transport}")

    if settings.identity.mcp_oidc_issuer:
        validator = oidc_validator or oidc_validator_from_settings()
        config = validator.config
        app = OIDCAuthMiddleware(app, validator)
        app = ProtectedResourceRouter(
            app,
            config=config,
            probe_app=health_app,
            probe_paths=PROBE_PATHS,
        )
        logger.info("OIDC resource-server auth ENABLED for %s transport.", transport)
    elif plain_token:
        app = BearerTokenAuthMiddleware(
            app,
            plain_token,
            actor_id=settings.server.mcp_legacy_actor_id,
            health_app=health_app,
            health_paths=PROBE_PATHS,
        )
        logger.info("Bearer-token auth ENABLED for %s transport.", transport)
    else:
        app = ProbeRouter(app)

    if transport == "streamable-http":
        app = MCPTransportSecurityMiddleware(
            app,
            mcp_app.settings.transport_security,
            mcp_path=mcp_app.settings.streamable_http_path,
        )

    app = MetricsRouter(
        app,
        path=settings.observability.metrics_path,
        enabled=settings.observability.metrics_enabled,
    )
    return RequestContextMiddleware(app)
