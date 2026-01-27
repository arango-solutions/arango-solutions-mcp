from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ArangoDBSettings(BaseSettings):
    """ArangoDB connection and configuration settings.

    Credentials are loaded from environment variables that should be configured
    in the MCP client's mcp.json configuration file.

    SSL/TLS Configuration:
    - When using https:// hosts, ARANGO_VERIFY_SSL must be true and 
      ARANGO_SSL_CERT_PATH must be provided
    - When using http:// hosts, SSL settings are optional (ignored)

    Example mcp.json environment variables (HTTPS with SSL):
    {
      "mcpServers": {
        "arangodb-mcp": {
          "command": "poetry",
          "args": ["run", "python", "main.py"],
          "env": {
            "ARANGO_HOSTS": "https://localhost:8530",
            "ARANGO_ROOT_USERNAME": "root",
            "ARANGO_ROOT_PASSWORD": "your_password_here",
            "ARANGO_DEFAULT_DB_NAME": "myapp",
            "ARANGO_VERIFY_SSL": "true",
            "ARANGO_SSL_CERT_PATH": "/path/to/certificate.pem"
          }
        }
      }
    }

    Example mcp.json environment variables (HTTP without SSL):
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
    hosts: str = Field(description="ArangoDB server URLs (e.g., http://localhost:8529 or https://localhost:8530)")
    root_username: str = Field(description="ArangoDB username")
    root_password: str = Field(description="ArangoDB password - REQUIRED via environment")
    default_db_name: str = Field(default="_system", description="Default database name")

    # Connection pool settings
    # NOTE: These parameters are currently unused (not passed to ArangoClient() in arango_connector.py)
    # They are kept for future implementation of connection pooling and timeout configuration
    max_connections: int = Field(default=50, description="Maximum concurrent connections")
    timeout: int = Field(default=30, description="Connection timeout in seconds")

    # SSL settings
    # These are conditionally required based on protocol in ARANGO_HOSTS:
    # - https:// → verify_ssl MUST be true, ssl_cert_path MUST be provided
    # - http:// → SSL settings are optional (will be ignored)
    verify_ssl: bool = Field(default=False, description="Verify SSL certificates - REQUIRED true for https:// hosts")
    ssl_cert_path: str = Field(
        default="", description="Path to SSL certificate file - REQUIRED for https:// hosts (supports cross-platform paths)"
    )

    # Internal: Store detected protocol for validation
    _detected_protocol: Optional[str] = None

    @field_validator("hosts")
    @classmethod
    def validate_hosts_protocol(cls, v: str) -> str:
        """Validate hosts and detect protocol (http or https).
        
        Ensures:
        - Hosts string is not empty
        - All hosts use the same protocol (no mixing http and https)
        - Protocol is detected and stored for SSL validation
        """
        if not v or not v.strip():
            raise ValueError("ARANGO_HOSTS cannot be empty. Provide at least one ArangoDB host.")

        # Parse hosts
        hosts = [host.strip() for host in v.split(",")]
        protocols = set()

        for host in hosts:
            if host.startswith("https://"):
                protocols.add("https")
            elif host.startswith("http://"):
                protocols.add("http")
            else:
                # No protocol specified - assume http (backwards compatible)
                protocols.add("http")

        # Check for mixed protocols
        if len(protocols) > 1:
            raise ValueError(
                f"Mixed protocols detected in ARANGO_HOSTS. "
                f"All hosts must use the same protocol (all http:// or all https://). "
                f"Found protocols: {', '.join(sorted(protocols))}"
            )

        return v

    @model_validator(mode="after")
    def validate_ssl_requirements(self) -> "ArangoDBSettings":
        """Validate SSL settings based on protocol and verify_ssl flag.
        
        Rules:
        1. http:// + verify_ssl=false → Valid (no SSL)
        2. http:// + verify_ssl=true  → Error (HTTP doesn't support SSL)
        3. https:// + verify_ssl=true → Valid (verify certificate)
        4. https:// + verify_ssl=false → Valid (skip verification, insecure)
        
        When verify_ssl=true, ssl_cert_path must be provided and valid.
        """
        # Detect protocol from first host
        first_host = self.hosts.split(",")[0].strip()
        
        if first_host.startswith("https://"):
            protocol = "https"
        elif first_host.startswith("http://"):
            protocol = "http"
        else:
            protocol = "http"  # Default
        
        # Store for use in other validators
        self._detected_protocol = protocol

        # Rule: HTTP cannot use SSL verification
        if protocol == "http" and self.verify_ssl:
            raise ValueError(
                "ARANGO_VERIFY_SSL cannot be 'true' when using http:// protocol. "
                "HTTP does not support SSL/TLS. Use https:// protocol for SSL connections."
            )
        
        # Rule: When verify_ssl=true, require and validate certificate path
        if self.verify_ssl:
            if not self.ssl_cert_path or self.ssl_cert_path.strip() == "":
                raise ValueError(
                    "ARANGO_SSL_CERT_PATH is required when ARANGO_VERIFY_SSL is 'true'. "
                    "Provide the full path to your CA certificate file.\n"
                    "Example: ARANGO_SSL_CERT_PATH=/opt/app/certs/arango.pem"
                )
            
            # Validate certificate file existence (path already normalized in field validator)
            cert_path = Path(self.ssl_cert_path)
            if not cert_path.exists():
                raise ValueError(
                    f"SSL certificate file not found at: {self.ssl_cert_path}\n"
                    f"Ensure the file exists and is readable.\n"
                    f"Check the path in ARANGO_SSL_CERT_PATH."
                )
            
            if not cert_path.is_file():
                raise ValueError(
                    f"SSL certificate path must be a file, not a directory: {self.ssl_cert_path}\n"
                    f"Point to a specific certificate file (e.g., /path/to/cert.pem)."
                )

        return self

    @field_validator("ssl_cert_path")
    @classmethod
    def validate_ssl_cert_path(cls, v: str) -> str:
        """Normalize SSL certificate path for cross-platform compatibility.
        
        Note: Path existence validation happens in validate_ssl_requirements()
        after protocol detection, since SSL is only required for https:// hosts.
        """
        if not v or not v.strip():
            return ""  # Empty is valid - will be checked in model_validator if https

        try:
            # Convert to Path object for cross-platform handling
            # Expand ~ for home directory and resolve to absolute path
            cert_path = Path(v).expanduser().resolve()
            
            # Return the resolved absolute path as string
            return str(cert_path)

        except Exception as e:
            raise ValueError(f"Invalid SSL certificate path '{v}': {e}") from e


class ServerSettings(BaseSettings):
    """MCP server configuration settings."""

    model_config = SettingsConfigDict(env_prefix="MCP_", env_file=".env", extra="ignore")

    server_name: str = "ArangoDB MCP Server"
    server_version: str = "1.0.0"
    log_level: str = "INFO"
    
    # Transport configuration
    transport: str = Field(
        default="stdio",
        description="Transport protocol: 'stdio' for local clients (Cursor, Claude Desktop) or 'http' for network access (Cline, OpenCode)"
    )
    
    # HTTP transport settings (used only when transport='http')
    http_host: str = Field(
        default="0.0.0.0",
        description="HTTP server bind address (0.0.0.0 for all interfaces, 127.0.0.1 for localhost only)"
    )
    http_port: int = Field(
        default=8000,
        description="HTTP server port"
    )


class AppSettings(BaseSettings):
    """Main application settings container."""
        # Keep server as a normal pydantic field
    server: ServerSettings = ServerSettings()

    # private backing attribute — not a pydantic-managed setting
    _arango: Optional[ArangoDBSettings] = None

    def get_arango_settings(self) -> ArangoDBSettings:
        """
        Lazily create ArangoDBSettings when needed. This avoids raising validation
        errors at import time but still gives a single place to initialize settings.
        """
        if self._arango is None:
            self._arango = ArangoDBSettings()
        return self._arango

    # Backwards-compatible property so existing code using `settings.arango` keeps working.
    @property
    def arango(self) -> ArangoDBSettings:
        return self.get_arango_settings()

# Global settings instance
settings = AppSettings()