"""
OpenCode server client for LLM and tool calling
"""
import httpx
from typing import Optional, Any
import time
from reasoner_pod.utils.logging import get_logger
from reasoner_pod.utils.metrics import metrics

logger = get_logger(__name__)


class OpenCodeClient:
    """
    Client for interacting with OpenCode server
    
    Based on verified OpenCode API endpoints at port 4099
    """
    
    def __init__(self, base_url: str = "http://host.docker.internal:4099", timeout: int = 120):
        """
        Initialize OpenCode client
        
        Args:
            base_url: OpenCode server URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self.session_id: Optional[str] = None
        
        logger.info(f"OpenCodeClient initialized with base_url={base_url}")
    
    async def health_check(self) -> bool:
        """
        Check if OpenCode server is healthy
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            start_time = time.time()
            response = await self.client.get(f"{self.base_url}/global/health")
            duration = time.time() - start_time
            
            success = response.status_code == 200
            metrics.record_opencode_request(
                operation="health_check",
                status="success" if success else "error",
                duration=duration
            )
            
            return success
        except Exception as e:
            logger.error(f"OpenCode health check failed: {e}")
            metrics.record_opencode_request(
                operation="health_check",
                status="error",
                duration=0
            )
            return False
    
    async def create_session(self, title: str) -> str:
        """
        Create a new OpenCode session
        
        Args:
            title: Session title
            
        Returns:
            Session ID
            
        Raises:
            Exception: If session creation fails
        """
        try:
            start_time = time.time()
            response = await self.client.post(
                f"{self.base_url}/session",
                json={"title": title}
            )
            response.raise_for_status()
            duration = time.time() - start_time
            
            session_data = response.json()
            self.session_id = session_data["id"]
            
            logger.info(f"Created OpenCode session: {self.session_id}")
            metrics.record_opencode_request(
                operation="create_session",
                status="success",
                duration=duration
            )
            
            return self.session_id
        
        except Exception as e:
            logger.error(f"Failed to create OpenCode session: {e}")
            metrics.record_opencode_request(
                operation="create_session",
                status="error",
                duration=time.time() - start_time
            )
            raise
    
    async def send_message(
        self,
        content: str,
        model: Optional[dict[str, str]] = None,
        agent: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Send a message to OpenCode and get response
        
        Args:
            content: Message content (user prompt)
            model: Model specification (providerID, modelID)
            agent: Agent mode - "plan" for planning, "build" for execution, None for regular
            session_id: Session ID (uses current session if not specified)
            
        Returns:
            Response from OpenCode with message and parts
            
        Raises:
            ValueError: If no session is active
            Exception: If message sending fails
        """
        target_session_id = session_id or self.session_id
        if not target_session_id:
            raise ValueError("No session created. Call create_session() first.")
        
        # Default model configuration
        if model is None:
            from reasoner_pod.config import settings
            model = {
                "providerID": settings.opencode_provider,
                "modelID": settings.opencode_model
            }
        
        payload = {
            "model": model,
            "parts": [
                {
                    "type": "text",
                    "text": content
                }
            ]
        }
        
        # Add agent if specified
        if agent:
            payload["agent"] = agent
        
        try:
            start_time = time.time()
            response = await self.client.post(
                f"{self.base_url}/session/{target_session_id}/message",
                json=payload
            )
            response.raise_for_status()
            duration = time.time() - start_time
            
            result = response.json()
            
            logger.info(
                f"OpenCode message sent successfully",
                extra={
                    "session_id": target_session_id,
                    "agent": agent or "default",
                    "duration_ms": round(duration * 1000, 2),
                    "response_keys": list(result.keys()) if result else []
                }
            )
            
            metrics.record_opencode_request(
                operation="send_message",
                status="success",
                duration=duration
            )
            
            return result
        
        except Exception as e:
            logger.error(
                f"Failed to send message to OpenCode: {e}",
                extra={"session_id": target_session_id, "agent": agent}
            )
            metrics.record_opencode_request(
                operation="send_message",
                status="error",
                duration=time.time() - start_time
            )
            raise
    
    async def get_messages(
        self,
        session_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """
        Get message history from session
        
        Args:
            session_id: Session ID (uses current session if not specified)
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of messages with parts
            
        Raises:
            ValueError: If no session is active
        """
        target_session_id = session_id or self.session_id
        if not target_session_id:
            raise ValueError("No session created.")
        
        try:
            start_time = time.time()
            params = {"limit": limit} if limit else {}
            response = await self.client.get(
                f"{self.base_url}/session/{target_session_id}/message",
                params=params
            )
            response.raise_for_status()
            duration = time.time() - start_time
            
            messages = response.json()
            
            metrics.record_opencode_request(
                operation="get_messages",
                status="success",
                duration=duration
            )
            
            return messages
        
        except Exception as e:
            logger.error(f"Failed to get messages from OpenCode: {e}")
            metrics.record_opencode_request(
                operation="get_messages",
                status="error",
                duration=time.time() - start_time
            )
            raise
    
    async def delete_session(self, session_id: Optional[str] = None) -> None:
        """
        Delete OpenCode session
        
        Args:
            session_id: Session ID to delete (uses current session if not specified)
        """
        target_session_id = session_id or self.session_id
        if not target_session_id:
            return
        
        try:
            start_time = time.time()
            await self.client.delete(f"{self.base_url}/session/{target_session_id}")
            duration = time.time() - start_time
            
            logger.debug(f"Deleted OpenCode session: {target_session_id}")
            metrics.record_opencode_request(
                operation="delete_session",
                status="success",
                duration=duration
            )
            
            if self.session_id == target_session_id:
                self.session_id = None
        
        except Exception as e:
            logger.error(f"Failed to delete OpenCode session: {e}")
            metrics.record_opencode_request(
                operation="delete_session",
                status="error",
                duration=time.time() - start_time
            )
    
    async def get_mcp_status(self) -> dict[str, Any]:
        """
        Get status of all registered MCP servers from OpenCode
        
        Returns:
            Dictionary mapping server names to their status
            Example: {"my-mcp-server": {"status": "connected", ...}, ...}
        """
        start_time = time.time()
        try:
            logger.debug(
                f"📊 Fetching MCP status from OpenCode",
                extra={"endpoint": f"{self.base_url}/mcp"}
            )
            
            response = await self.client.get(f"{self.base_url}/mcp")
            response.raise_for_status()
            duration = time.time() - start_time
            
            mcp_status = response.json()
            
            # Count connected vs disconnected servers
            connected_count = sum(1 for s in mcp_status.values() if s.get("status") == "connected")
            total_count = len(mcp_status)
            
            logger.info(
                f"✅ Retrieved MCP status",
                extra={
                    "total_servers": total_count,
                    "connected": connected_count,
                    "disconnected": total_count - connected_count,
                    "servers": list(mcp_status.keys()),
                    "duration_ms": round(duration * 1000, 2)
                }
            )
            
            metrics.record_opencode_request(
                operation="get_mcp_status",
                status="success",
                duration=duration
            )
            
            return mcp_status
        
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"❌ Failed to get MCP status",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration * 1000, 2)
                },
                exc_info=True
            )
            metrics.record_opencode_request(
                operation="get_mcp_status",
                status="error",
                duration=duration
            )
            return {}
    
    async def list_mcp_tools(self) -> dict[str, Any]:
        """
        List all available MCP tools via OpenCode experimental endpoint
        
        Returns:
            Dictionary of available tool IDs
        """
        try:
            start_time = time.time()
            response = await self.client.get(f"{self.base_url}/experimental/tool/ids")
            response.raise_for_status()
            duration = time.time() - start_time
            
            tools = response.json()
            
            logger.info(f"Retrieved MCP tools list")
            
            metrics.record_opencode_request(
                operation="list_mcp_tools",
                status="success",
                duration=duration
            )
            
            return tools
        
        except Exception as e:
            logger.error(f"Failed to list MCP tools: {e}", exc_info=True)
            metrics.record_opencode_request(
                operation="list_mcp_tools",
                status="error",
                duration=time.time() - start_time
            )
            return {}
    
    async def close(self) -> None:
        """Close the HTTP client"""
        await self.client.aclose()
        logger.debug("OpenCode client closed")


