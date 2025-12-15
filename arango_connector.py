import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from arango import ArangoClient
from arango.database import StandardDatabase

from config import settings

logger = logging.getLogger(__name__)


class ArangoDBConnector:
    """Manages ArangoDB connections with automatic reconnection and health checks.
    
    Supports both HTTP and HTTPS connections with SSL certificate verification.
    """

    def __init__(self):
        self.client: Optional[ArangoClient] = None
        self._default_db: Optional[StandardDatabase] = None

    def _detect_protocol(self, hosts_string: str) -> str:
        """Detect protocol (http or https) from hosts configuration.
        
        Args:
            hosts_string: Comma-separated list of hosts
            
        Returns:
            "http" or "https"
        """
        first_host = hosts_string.split(",")[0].strip()
        
        if first_host.startswith("https://"):
            return "https"
        elif first_host.startswith("http://"):
            return "http"
        else:
            return "http"  # Default to http

    def connect(self) -> None:
        """Establish connection to ArangoDB cluster.
        
        For HTTPS connections, SSL certificate verification is performed using
        the certificate specified in ARANGO_SSL_CERT_PATH.
        
        For HTTP connections, no SSL verification is performed.
        """
        try:
            # Validate required credentials are provided
            if not settings.arango.root_username:
                raise ValueError(
                    "ArangoDB username not configured. Please set ARANGO_ROOT_USERNAME via MCP client JSON configuration."
                )

            if not settings.arango.root_password:
                raise ValueError(
                    "ArangoDB password not configured. Please set ARANGO_ROOT_PASSWORD via MCP client JSON configuration."
                )

            # Validate that hosts are configured
            if not settings.arango.hosts:
                raise ValueError(
                    "ArangoDB hosts not configured. Please set ARANGO_HOSTS via MCP client JSON configuration."
                )

            # Parse hosts if multiple are provided
            hosts = [host.strip() for host in settings.arango.hosts.split(",")]
            
            # Detect protocol to determine if SSL should be used
            protocol = self._detect_protocol(settings.arango.hosts)

            logger.info(
                f"Connecting to ArangoDB at: {hosts} as user: {settings.arango.root_username}"
            )

            # Create ArangoClient based on protocol and SSL verification setting
            if protocol == "https":
                if settings.arango.verify_ssl:
                    # HTTPS with certificate verification
                    verify_override = settings.arango.ssl_cert_path
                    logger.info("Using HTTPS with SSL certificate verification enabled")
                    logger.info(f"SSL certificate path: {verify_override}")
                    self.client = ArangoClient(hosts=hosts, verify_override=verify_override)
                else:
                    # HTTPS without certificate verification (insecure, for dev/testing)
                    logger.warning("Using HTTPS with SSL verification DISABLED (insecure)")
                    logger.warning("This should only be used in development with self-signed certificates")
                    self.client = ArangoClient(hosts=hosts, verify_override=False)
            else:
                # HTTP connection (no SSL)
                logger.info("Using HTTP connection (non-SSL)")
                self.client = ArangoClient(hosts=hosts)

            self._default_db = self.client.db(
                settings.arango.default_db_name,
                username=settings.arango.root_username,
                password=settings.arango.root_password,
            )

            server_info = self._default_db.version()
            logger.info(f"Successfully connected to ArangoDB. Server version: {server_info}")

        except ValueError as e:  # Catch our specific configuration errors
            logger.error(f"Configuration error: {e}")
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "ssl" in error_msg or "certificate" in error_msg:
                logger.error(
                    f"SSL certificate verification failed: {e}. "
                    f"Check certificate at: {settings.arango.ssl_cert_path}"
                )
            elif "connection" in error_msg or "connect" in error_msg:
                logger.error(f"Failed to connect to ArangoDB: {e}")
            elif "authentication" in error_msg or "unauthorized" in error_msg:
                logger.error(f"Database authentication failed: {e}")
            else:
                logger.error(f"ArangoDB connection error: {e}")
            raise

    def disconnect(self) -> None:
        """Close ArangoDB connections."""
        try:
            if self.client:
                logger.info("Disconnecting from ArangoDB")
                self.client.close()
                self.client = None
                self._default_db = None
        except Exception as e:
            logger.warning(f"Error during ArangoDB disconnection: {e}")

    def get_db(self, db_name: Optional[str] = None) -> StandardDatabase:
        """Get database instance with authentication."""
        if not self.client:
            raise RuntimeError("ArangoDB client not initialized. Call connect() first.")

        database_name = db_name or settings.arango.default_db_name

        return self.client.db(
            database_name,
            username=settings.arango.root_username,
            password=settings.arango.root_password,
        )

    def health_check(self) -> bool:
        """Check if ArangoDB connection is healthy."""
        try:
            if not self.client or not self._default_db:
                return False

            self._default_db.properties()
            return True
        except Exception:
            return False


# Global connector instance
arango_connector = ArangoDBConnector()


@asynccontextmanager
async def arango_db_lifespan(mcp_server_instance) -> AsyncIterator[ArangoDBConnector]:
    """Lifespan context manager for MCP server with ArangoDB connection management."""
    logger.info("Starting ArangoDB MCP Server...")

    try:
        arango_connector.connect()
        logger.info("ArangoDB connection established successfully")

        yield arango_connector

    except Exception as e:
        logger.error(f"Failed to initialize ArangoDB connection: {e}")
        raise
    finally:
        logger.info("Shutting down ArangoDB MCP Server...")
        arango_connector.disconnect()
        logger.info("ArangoDB connection closed")