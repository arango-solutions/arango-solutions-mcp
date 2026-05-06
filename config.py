from pathlib import Path
from typing import Optional

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
          "args": ["run", "python", "main.py"],
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
        "exceed this. Set to 0 to disable. Per-call overrides via the execute-aql-query tool.",
    )
    log_aql_queries: bool = Field(
        default=False,
        description="When false (default), the AQL execution agent logs only structural "
        "metadata (query length, bind variable keys, database, operation). User-supplied "
        "AQL can contain literal sensitive values (e.g. FILTER doc.token == \"abc\"), so "
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


class AppSettings(BaseSettings):
    """Main application settings container."""

    arango: ArangoDBSettings = ArangoDBSettings()
    server: ServerSettings = ServerSettings()


# Global settings instance
settings = AppSettings()
