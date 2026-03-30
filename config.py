from pathlib import Path

from pydantic import Field, field_validator
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
    root_password: str = Field(description="ArangoDB password - REQUIRED via environment")
    default_db_name: str = Field(default="_system", description="Default database name")

    # Connection pool settings
    max_connections: int = Field(default=50, description="Maximum concurrent connections (reserved, not yet wired)")
    timeout: int = Field(default=30, description="Connection timeout in seconds (reserved, not yet wired)")

    # SSL settings
    verify_ssl: bool = Field(default=False, description="Verify SSL certificates")
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
    enable_metrics: bool = Field(default=False, description="Enable metrics collection (reserved, not yet wired)")


class AppSettings(BaseSettings):
    """Main application settings container."""

    arango: ArangoDBSettings = ArangoDBSettings()
    server: ServerSettings = ServerSettings()


# Global settings instance
settings = AppSettings()
