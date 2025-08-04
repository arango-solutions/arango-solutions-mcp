import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from arango import ArangoClient, ArangoServerError
from arango.database import StandardDatabase
from arango.exceptions import DatabaseCreateError

from .config import settings


class ArangoDBConnector:
    def __init__(self):
        self.client: Optional[ArangoClient] = None
        self.db: Optional[StandardDatabase] = None
        self._lock = asyncio.Lock()  # For ensuring thread-safe init

    async def connect(self) -> None:
        async with self._lock:
            if not self.client:
                self.client = ArangoClient(hosts=settings.arango.hosts)

            if not self.db:
                sys_db = self.client.db(
                    "_system",
                    username=settings.arango.root_username,
                    password=settings.arango.root_password,
                )

                # Ensure the default database exists
                if (
                    not sys_db.has_database(settings.arango.default_db_name)
                    and settings.arango.default_db_name != "_system"
                ):
                    try:
                        sys_db.create_database(settings.arango.default_db_name)
                        print(f"Database '{settings.arango.default_db_name}' created.")
                    except (DatabaseCreateError, ArangoServerError) as e:
                        print(
                            f"Failed to create database '{settings.arango.default_db_name}': {e}"
                        )
                        # Fallback to _system if creation fails and it's not _system itself
                        if settings.arango.default_db_name != "_system":
                            print(f"Falling back to _system database.")
                        else:  # if _system itself fails, then critical error
                            raise

                self.db = self.client.db(
                    settings.arango.default_db_name,
                    username=settings.arango.root_username,
                    password=settings.arango.root_password,
                )
                print(f"Connected to ArangoDB database: {self.db.name}")

    async def disconnect(self) -> None:
        async with self._lock:
            if self.client:
                # ArangoClient doesn't have an explicit close/disconnect method in python-arango
                # Connections are typically managed per request or pooled by the HTTP client.
                # We'll just reset the client and db instance here.
                self.client = None
                self.db = None
                print("ArangoDB connection resources released.")

    def get_db(self) -> StandardDatabase:
        if not self.db:
            raise ConnectionError("ArangoDB is not connected. Call connect() first.")
        return self.db


# Global connector instance
arango_connector = ArangoDBConnector()


@asynccontextmanager
async def arango_db_lifespan(mcp_server_instance) -> AsyncIterator[ArangoDBConnector]:
    """Lifespan manager for ArangoDB connection."""
    await arango_connector.connect()
    try:
        yield arango_connector
    finally:
        await arango_connector.disconnect()
