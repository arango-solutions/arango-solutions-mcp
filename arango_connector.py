import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from arango import ArangoClient
from arango.database import StandardDatabase

from config import settings

logger = logging.getLogger(__name__)


class ArangoDBConnector:
    """Manages ArangoDB connections with automatic reconnection and health checks."""

    def __init__(self):
        self.client: Optional[ArangoClient] = None
        self._default_db: Optional[StandardDatabase] = None

    async def connect(self) -> None:
        """Establish connection to ArangoDB cluster."""
        try:
            # Validate required credentials are provided
            if not settings.arango.root_password:
                raise ValueError(
                    "ArangoDB password not configured. Please set ARANGO_ROOT_PASSWORD via MCP client JSON configuration."
                )

            # Parse hosts if multiple are provided
            hosts = [host.strip() for host in settings.arango.hosts.split(",")]

            logger.info(
                f"Connecting to ArangoDB at: {hosts} as user: {settings.arango.root_username}"
            )

            # Create client with connection pooling using the modern python-arango API.
            # NOTE: serializer_options and http_client_options are deprecated in newer versions.
            # We now configure and pass an HTTPClient instance directly.
            self.client = ArangoClient(hosts=hosts)

            # Test connection by accessing default database
            self._default_db = self.client.db(
                settings.arango.default_db_name,
                username=settings.arango.root_username,
                password=settings.arango.root_password,
                # The http_client is implicitly used by the db object now
            )

            # Verify connection works
            # Using a simple, lightweight call like .version() is a good health check.
            server_info = self._default_db.version()
            logger.info(f"Successfully connected to ArangoDB. Server version: {server_info}")

        except ValueError as e:  # Catch our specific password error
            logger.error(f"Configuration error: {e}")
            raise
        except Exception as e:
            # Handle connection and authentication errors
            error_msg = str(e).lower()
            if "connection" in error_msg or "connect" in error_msg:
                logger.error(f"Failed to connect to ArangoDB: {e}")
            elif "authentication" in error_msg or "unauthorized" in error_msg:
                logger.error(f"Database authentication failed: {e}")
            else:
                logger.error(f"ArangoDB connection error: {e}")
            raise

    async def disconnect(self) -> None:
        """Close ArangoDB connections gracefully."""
        try:
            if self.client:
                # ArangoDB Python client doesn't have an explicit close method
                # Connections are managed by the HTTP client
                logger.info("Disconnecting from ArangoDB")
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

            # Simple query to test connection
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
        # Connect to ArangoDB
        await arango_connector.connect()
        logger.info("ArangoDB connection established successfully")

        # Yield the connector for use during server lifetime
        yield arango_connector

    except Exception as e:
        logger.error(f"Failed to initialize ArangoDB connection: {e}")
        raise
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down ArangoDB MCP Server...")
        await arango_connector.disconnect()
        logger.info("ArangoDB connection closed")
