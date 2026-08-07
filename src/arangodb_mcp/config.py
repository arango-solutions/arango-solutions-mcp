from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ArangoDBSettings(BaseSettings):
    """ArangoDB connection and configuration settings.

    Credentials are loaded from environment variables that should be configured
    in the MCP client's mcp.json configuration file.

    Example mcp.json environment variables:
    {
      "mcpServers": {
        "arangodb-mcp": {
          "command": "poetry",
          "args": ["run", "arangodb-mcp"],
          "env": {
            "ARANGO_HOSTS": "http://localhost:8529",
            "ARANGO_ROOT_USERNAME": "root",
            "ARANGO_ROOT_PASSWORD": "your_password_here",
            "ARANGO_DEFAULT_DB_NAME": "myapp"
          }
        }
      }
    }
    """

    model_config = SettingsConfigDict(env_prefix="ARANGO_", env_file=".env", extra="ignore")

    # Connection settings - MUST be provided via environment variables
    hosts: str = Field(description="ArangoDB server URLs (e.g., http://localhost:8529)")
    root_username: str = Field(description="ArangoDB username")
    root_password: SecretStr = Field(description="ArangoDB password - REQUIRED via environment")
    default_db_name: str = Field(default="_system", description="Default database name")

    # SSL settings
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    ssl_cert_path: str = Field(
        default="", description="Path to SSL certificate file (supports cross-platform paths)"
    )

    @field_validator("ssl_cert_path")
    @classmethod
    def validate_ssl_cert_path(cls, v: str) -> str:
        """Validate and normalize SSL certificate path for cross-platform compatibility."""
        if not v:  # Empty string is valid (no SSL cert)
            return v

        try:
            # Convert to Path object for cross-platform handling
            cert_path = Path(v).resolve()

            # Check if file exists (only if path is provided)
            if not cert_path.exists():
                raise ValueError(f"SSL certificate file not found: {cert_path}")

            if not cert_path.is_file():
                raise ValueError(f"SSL certificate path is not a file: {cert_path}")

            # Return the resolved absolute path as string
            return str(cert_path)

        except Exception as e:
            raise ValueError(f"Invalid SSL certificate path '{v}': {e}") from e


class ServerSettings(BaseSettings):
    """MCP server configuration settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    server_name: str = "ArangoDB MCP Server"
    server_version: str = "2.0.0"
    log_level: str = "INFO"
    log_format: str = Field(
        default="text",
        description="Log format: 'text' for human-readable (default), "
        "'json' for one-line JSON per record (production / log aggregation).",
    )
    mcp_transport: str = Field(
        default="stdio",
        description="MCP transport protocol: 'stdio' for client-launched, "
        "'sse' or 'streamable-http' for standalone/Docker deployment.",
    )
    mcp_host: str = Field(
        default="0.0.0.0",
        description="Host to bind when using sse or streamable-http transport.",
    )
    mcp_port: int = Field(
        default=8000,
        description="Port to bind when using sse or streamable-http transport.",
    )
    enable_js_transactions: bool = Field(
        default=False,
        description="Enable server-side JavaScript transaction execution (execute-transaction tool). "
        "Disabled by default because it allows arbitrary JS on the database server.",
    )
    default_aql_max_runtime: float = Field(
        default=30.0,
        description="Default per-query AQL max runtime in seconds. ArangoDB will kill queries that "
        "exceed this. Values outside 0-30 are clamped to the non-disableable 30-second production "
        "ceiling. Per-call overrides cannot exceed or disable that ceiling.",
    )
    log_aql_queries: bool = Field(
        default=False,
        description="When false (default), the AQL execution agent logs only structural "
        "metadata (query length, bind variable keys, database, operation). User-supplied "
        'AQL can contain literal sensitive values (e.g. FILTER doc.token == "abc"), so '
        "the query text is suppressed. Set true to log the first 100 chars of the query "
        "for debugging.",
    )
    connect_max_retries: int = Field(
        default=5,
        description="Max connection retries on transient failures at startup. "
        "Set to 0 to disable retries.",
    )
    connect_initial_backoff: float = Field(
        default=1.0,
        description="Initial backoff (seconds) between connection retries; "
        "doubled each attempt up to 30s.",
    )
    mcp_auth_token: Optional[SecretStr] = Field(
        default=None,
        description="Optional bearer token required for sse / streamable-http transports. "
        "When unset and binding non-loopback, the server refuses to start. Ignored for stdio.",
    )
    mcp_protocol_mode: Literal["strict", "legacy", "auto"] = Field(
        default="auto",
        description="MCP HTTP compatibility mode. 'strict' and 'auto' use stateless HTTP; "
        "'legacy' retains session-oriented behavior during the v2 compatibility window.",
    )
    mcp_dns_rebinding_protection: bool = Field(
        default=True,
        description="Validate Host and Origin headers on MCP HTTP transports.",
    )
    mcp_allowed_hosts: str = Field(
        default="127.0.0.1:*,localhost:*,[::1]:*",
        description="Comma-separated Host header allowlist; entries may use a ':*' port wildcard.",
    )
    mcp_allowed_origins: str = Field(
        default="http://127.0.0.1:*,http://localhost:*,http://[::1]:*",
        description="Comma-separated browser Origin allowlist; entries may use a ':*' wildcard.",
    )
    mcp_profile: Literal["readonly", "developer", "operator", "admin"] = Field(
        default="readonly",
        description="Base tool exposure profile. Version 3 defaults to the compact readonly surface.",
    )
    mcp_toolsets: str = Field(
        default="",
        description="Comma-separated additive toolsets. Supported values: graph, search.",
    )
    mcp_denied_tools: str = Field(
        default="",
        description="Comma-separated tool names removed after profile resolution.",
    )
    mcp_denied_categories: str = Field(
        default="",
        description="Comma-separated catalog categories removed after profile resolution.",
    )
    mcp_result_contract: Literal["v3", "legacy"] = Field(
        default="v3",
        description="Tool result contract. Legacy compatibility expires on 2027-02-01.",
    )
    mcp_legacy_actor_id: str = Field(
        default="legacy-http",
        description="Server-established actor ID for the temporary shared-token HTTP mode.",
    )
    mcp_confirmation_secret: Optional[SecretStr] = Field(
        default=None,
        description="Server-local HMAC key used only by the out-of-band confirmation minting CLI.",
    )


class EmbeddingSettings(BaseSettings):
    """Embedding-provider settings for the shared-memory / pattern tools.

    Configures the OpenAI embeddings REST API used by embed-text, embed-document,
    pattern-search and save-pattern. Both fields are optional: when
    OPENAI_API_KEY is unset the embedding/pattern tools degrade gracefully
    (pattern-search falls back to BM25; save-pattern defers the vector), so the
    core 74-tool database server runs unaffected without them.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: Optional[SecretStr] = Field(
        default=None,
        description="OpenAI API key for the embeddings endpoint (env: OPENAI_API_KEY). "
        "Required for vector/hybrid pattern-search and for embedding new patterns; "
        "when unset the pattern tools degrade to keyword-only (BM25) behaviour.",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model (env: EMBEDDING_MODEL). "
        "text-embedding-3-small = 1536 dimensions.",
    )


class IdentitySettings(BaseSettings):
    """OAuth/OIDC resource-server and trusted credential-provider settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mcp_oidc_issuer: str = Field(
        default="",
        description="OIDC issuer URL. Setting this enables OIDC HTTP authentication.",
    )
    mcp_oidc_audience: str = Field(
        default="",
        description="Required JWT audience for this MCP resource server.",
    )
    mcp_resource_url: str = Field(
        default="",
        description="Canonical protected resource URL advertised through RFC 9728 metadata.",
    )
    mcp_oidc_algorithms: str = Field(
        default="RS256",
        description="Comma-separated asymmetric JWT signing algorithms.",
    )
    mcp_oidc_actor_claim: str = Field(
        default="sub",
        description="Validated JWT claim used as the request actor identifier.",
    )
    mcp_oidc_database_claim: str = Field(
        default="arangodb_databases",
        description="JWT claim containing the database allowlist.",
    )
    mcp_oidc_clock_skew_seconds: int = Field(
        default=30,
        ge=0,
        le=300,
        description="JWT expiry/not-before validation leeway.",
    )
    mcp_oidc_cache_ttl_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Fallback OIDC discovery/JWKS cache lifetime.",
    )
    mcp_oidc_allow_insecure_http: bool = Field(
        default=False,
        description=(
            "Allow HTTP OIDC endpoints only for loopback, single-label container hosts, "
            "private IPs, or .test/.local names. Test/development only; production defaults "
            "fail closed."
        ),
    )
    mcp_arango_credentials_json: Optional[SecretStr] = Field(
        default=None,
        description="Trusted actor-to-ArangoDB credential mapping; never sourced from JWT claims.",
    )


class ObservabilitySettings(BaseSettings):
    """Metrics, tracing, and multi-tenant limiter settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    metrics_enabled: bool = Field(default=True, description="Expose Prometheus metrics over HTTP.")
    metrics_path: str = Field(default="/metrics", description="Prometheus scrape path.")
    otel_traces_exporter: Literal["none", "otlp"] = Field(
        default="none",
        description="Trace exporter. OTLP uses HTTP/protobuf on the configured endpoint.",
    )
    otel_service_name: str = Field(default="arangodb-mcp-server")
    otel_service_version: str = Field(default="2.0.0")
    otel_exporter_otlp_endpoint: str = Field(default="http://localhost:4318")
    otel_exporter_otlp_headers: SecretStr = Field(default=SecretStr(""))
    otel_exporter_otlp_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    mcp_actor_rate_limit_per_minute: int = Field(default=600, ge=1, le=1_000_000)
    mcp_actor_rate_limit_burst: int = Field(default=200, ge=1, le=100_000)
    mcp_global_max_concurrency: int = Field(default=64, ge=1, le=10_000)
    mcp_class_concurrency_limits: str = Field(
        default="standard=32,query=16,bulk=8,control=4,external=8",
        description="Comma-separated catalog limit-class concurrency ceilings.",
    )
    mcp_limiter_retry_after_ms: int = Field(default=250, ge=1, le=60_000)

    @field_validator("metrics_path")
    @classmethod
    def validate_metrics_path(cls, value: str) -> str:
        if not value.startswith("/") or " " in value:
            raise ValueError("METRICS_PATH must be an absolute URL path")
        return value


class AppSettings(BaseSettings):
    """Main application settings container."""

    arango: ArangoDBSettings = ArangoDBSettings()
    server: ServerSettings = ServerSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    identity: IdentitySettings = IdentitySettings()
    observability: ObservabilitySettings = ObservabilitySettings()


# Global settings instance
settings = AppSettings()
