import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from arango import ArangoClient
from arango.database import StandardDatabase

from config import settings

logger = logging.getLogger(__name__)


def _is_auth_error(exc: Exception) -> bool:
    """Detect authentication / authorization failures that must NOT be retried."""
    msg = str(exc).lower()
    if "authentication" in msg or "unauthorized" in msg or "forbidden" in msg:
        return True
    http_code = getattr(exc, "http_code", None)
    return http_code in (401, 403)


class ArangoDBConnector:
    """Manages ArangoDB connections with automatic reconnection and health checks."""

    def __init__(self) -> None:
        self.client: Optional[ArangoClient] = None
        self._default_db: Optional[StandardDatabase] = None
        self._server_version: Optional[str] = None

    @property
    def server_version(self) -> Optional[str]:
        return self._server_version

    def _connect_sync(self) -> None:
        """Synchronous connection logic, run via asyncio.to_thread."""
        if not settings.arango.root_password.get_secret_value():
            raise ValueError(
                "ArangoDB password not configured. "
                "Set ARANGO_ROOT_PASSWORD via MCP client JSON configuration."
            )

        hosts = [host.strip() for host in settings.arango.hosts.split(",")]

        logger.info(f"Connecting to ArangoDB at: {hosts} as user: {settings.arango.root_username}")

        client_kwargs: dict = {"hosts": hosts}

        if settings.arango.verify_ssl:
            client_kwargs["verify_override"] = True
            if settings.arango.ssl_cert_path:
                client_kwargs["verify_override"] = settings.arango.ssl_cert_path
        else:
            client_kwargs["verify_override"] = False

        self.client = ArangoClient(**client_kwargs)

        # Ensure the target database exists before connecting to it (create-if-missing).
        # Guarded so a user lacking _system access does not break connecting to an
        # already-existing database.
        db_name = settings.arango.default_db_name
        if db_name != "_system":
            try:
                sys_db = self.client.db(
                    "_system",
                    username=settings.arango.root_username,
                    password=settings.arango.root_password.get_secret_value(),
                )
                if not sys_db.has_database(db_name):
                    logger.info(f"Database '{db_name}' does not exist; creating it.")
                    sys_db.create_database(db_name)
            except Exception as e:
                logger.warning(
                    f"Could not ensure database '{db_name}' exists (continuing; "
                    f"it may already exist or the user may lack _system access): {e}"
                )

        self._default_db = self.client.db(
            db_name,
            username=settings.arango.root_username,
            password=settings.arango.root_password.get_secret_value(),
        )

        self._server_version = self._default_db.version()
        logger.info(f"Connected to ArangoDB server version: {self._server_version}")

    async def connect(self) -> None:
        """Establish connection to ArangoDB with retry/backoff on transient failures.

        Retries are skipped for configuration errors (``ValueError``) and
        authentication failures so misconfiguration fails fast instead of looping.
        """
        max_retries = settings.server.connect_max_retries
        backoff = settings.server.connect_initial_backoff

        last_exc: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                await asyncio.to_thread(self._connect_sync)
                return
            except ValueError as e:
                logger.error(f"Configuration error: {e}")
                raise
            except Exception as e:
                if _is_auth_error(e):
                    logger.error(f"Database authentication failed: {e}")
                    raise

                last_exc = e
                error_msg = str(e).lower()
                if "connection" in error_msg or "connect" in error_msg:
                    log_label = "Failed to connect to ArangoDB"
                else:
                    log_label = "ArangoDB connection error"

                if attempt >= max_retries:
                    break

                logger.warning(
                    "%s on attempt %d/%d: %s. Retrying in %.1fs…",
                    log_label,
                    attempt + 1,
                    max_retries + 1,
                    e,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

        logger.error(
            "Failed to connect to ArangoDB after %d attempts: %s",
            max_retries + 1,
            last_exc,
        )
        assert last_exc is not None
        raise last_exc

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
            password=settings.arango.root_password.get_secret_value(),
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
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
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
