import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .config import client_settings


class MCPClientManager:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session: Optional[ClientSession] = None
        self._lock = asyncio.Lock()
        self._client_cm = None  # To store the streamablehttp_client context manager
        self._session_cm = None  # To store the ClientSession context manager

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[ClientSession]:
        async with self._lock:
            if (
                self.session and not self.session._write_stream.is_closed
            ):  # Check if stream is still open
                yield self.session
                return

            print(f"Connecting to MCP Server at {self.server_url}...")
            # Clean up previous context managers if they exist and are closable
            if self._session_cm and hasattr(self._session_cm, "__aexit__"):
                try:
                    await self._session_cm.__aexit__(None, None, None)
                except Exception:
                    pass
            if self._client_cm and hasattr(self._client_cm, "__aexit__"):
                try:
                    await self._client_cm.__aexit__(None, None, None)
                except Exception:
                    pass

            self._client_cm = streamablehttp_client(self.server_url)
            read_stream, write_stream, _ = await self._client_cm.__aenter__()

            self._session_cm = ClientSession(read_stream, write_stream)
            self.session = await self._session_cm.__aenter__()

            try:
                print("Initializing MCP session...")
                await self.session.initialize()
                print("MCP session initialized.")
                yield self.session
            finally:
                print("Closing MCP session from get_session context manager...")
                if self._session_cm:
                    await self._session_cm.__aexit__(None, None, None)
                    self.session = None  # Mark as closed
                    self._session_cm = None
                if self._client_cm:
                    await self._client_cm.__aexit__(None, None, None)
                    self._client_cm = None


mcp_client_manager = MCPClientManager(str(client_settings.mcp_server_url))


async def app_lifespan(app):  # app is FastAPI instance
    # This ensures the initial connection is tried at startup,
    # but get_session will handle reconnections if needed.
    # We don't keep the session open globally here, get_session will manage it.
    print("FastAPI app starting up, MCPClientManager initialized.")
    yield
    # Cleanup on shutdown (optional, as get_session handles its own cleanup)
    print(
        "FastAPI app shutting down. MCPClientManager will clean up on next get_session if needed."
    )
