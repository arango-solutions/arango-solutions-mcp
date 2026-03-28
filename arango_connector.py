import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from arango import ArangoClient
from arango.database import StandardDatabase

from config import settings

logger = logging.getLogger(__name__)


class ArangoDBConnector:
    """Manages ArangoDB connections with automatic reconnection and health checks."""

    def __init__(self) -> None:
        self.client: Optional[ArangoClient] = None
        self._default_db: Optional[StandardDatabase] = None
        self._server_version: Optional[str] = None

    @property
    def server_version(self) -> Optional[str]:
        return self._server_version

    async def connect(self) -> None:
        """Establish connection to ArangoDB."""
        try:
            if not settings.arango.root_password:
                raise ValueError(
                    "ArangoDB password not configured. "
                    "Set ARANGO_ROOT_PASSWORD via MCP client JSON configuration."
                )

            hosts = [host.strip() for host in settings.arango.hosts.split(",")]

            logger.info(
                f"Connecting to ArangoDB at: {hosts} as user: {settings.arango.root_username}"
            )

            client_kwargs: dict = {"hosts": hosts}

            if settings.arango.verify_ssl:
                client_kwargs["verify_override"] = True
                if settings.arango.ssl_cert_path:
                    client_kwargs["verify_override"] = settings.arango.ssl_cert_path
            else:
                client_kwargs["verify_override"] = False

            self.client = ArangoClient(**client_kwargs)

            self._default_db = self.client.db(
                settings.arango.default_db_name,
                username=settings.arango.root_username,
                password=settings.arango.root_password,
            )

            self._server_version = self._default_db.version()
            logger.info(f"Connected to ArangoDB server version: {self._server_version}")

        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            raise
        except Exception as e:
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
                logger.info("Disconnecting from ArangoDB")
                self.client = None
                self._default_db = None
                self._server_version = None
        except Exception as e:
            logger.warning(f"Error during ArangoDB disconnection: {e}")

    def get_db(self, db_name: Optional[str] = None) -> StandardDatabase:
        """Get an authenticated database handle.

        All agents should use this instead of manually calling client.db().
        """
        if not self.client:
            raise RuntimeError("ArangoDB client not initialized. Call connect() first.")

        database_name = db_name or settings.arango.default_db_name

        return self.client.db(
            database_name,
            username=settings.arango.root_username,
            password=settings.arango.root_password,
        )

    def get_system_db(self) -> StandardDatabase:
        """Get an authenticated handle to the _system database."""
        return self.get_db("_system")

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
