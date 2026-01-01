"""
MCP (Model Context Protocol) Management API Routes
"""
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from reasoner_pod.utils.logging import get_logger
from reasoner_pod.clients.opencode import OpenCodeClient
from reasoner_pod.config import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/mcp", tags=["MCP Management"])


class MCPConfig(BaseModel):
    """MCP Server Configuration"""
    type: str = Field(default="local", description="MCP server type")
    command: list[str] = Field(..., description="Docker command array for running MCP server")
    enabled: bool = Field(default=True, description="Whether the MCP server is enabled")


class MCPRegistrationRequest(BaseModel):
    """Request model for MCP registration"""
    name: str = Field(..., description="MCP server name (e.g., 'my-mcp-server')")
    config: MCPConfig = Field(..., description="MCP server configuration")


class MCPRegistrationResponse(BaseModel):
    """Response model for MCP registration"""
    success: bool = Field(..., description="Whether registration was successful")
    message: str = Field(..., description="Status message")
    server_name: str = Field(..., description="Name of the registered MCP server")


@router.post("/register", response_model=MCPRegistrationResponse)
async def register_mcp_server(
    request: MCPRegistrationRequest = Body(
        ...,
        example={
            "name": "my-mcp-server",
            "config": {
                "type": "local",
                "command": [
                    "docker",
                    "run",
                    "-i",
                    "--rm",
                    "your-mcp-server:latest"
                ],
                "enabled": True
            }
        }
    )
) -> MCPRegistrationResponse:
    """
    Register an MCP server with OpenCode
    
    This endpoint forwards the MCP registration request to the OpenCode API.
    Use this to register any MCP server on-demand.
    
    **Example Request:**
    ```json
    {
        "name": "my-mcp-server",
        "config": {
            "type": "local",
            "command": [
                "docker", "run", "-i", "--rm",
                "your-mcp-server:latest"
            ],
            "enabled": true
        }
    }
    ```
    
    **Returns:**
    - success: Boolean indicating if registration was successful
    - message: Status message with details
    - server_name: Name of the registered MCP server
    """
    logger.info(
        f"📥 Received MCP registration request for server: {request.name}",
        extra={
            "server_name": request.name,
            "config_type": request.config.type,
            "enabled": request.config.enabled
        }
    )
    
    opencode = OpenCodeClient(base_url=settings.opencode_base_url)
    
    try:
        # Prepare payload for OpenCode API
        payload = {
            "name": request.name,
            "config": {
                "type": request.config.type,
                "command": request.config.command,
                "enabled": request.config.enabled
            }
        }
        
        logger.info(
            f"🔧 Forwarding MCP registration to OpenCode",
            extra={
                "opencode_url": f"{settings.opencode_base_url}/mcp",
                "payload": payload
            }
        )
        
        # Call OpenCode API directly
        response = await opencode.client.post(
            f"{settings.opencode_base_url}/mcp",
            json=payload
        )
        
        # Check response
        if response.status_code == 200:
            logger.info(
                f"✅ MCP server '{request.name}' registered successfully",
                extra={
                    "server_name": request.name,
                    "status_code": response.status_code
                }
            )
            
            return MCPRegistrationResponse(
                success=True,
                message=f"MCP server '{request.name}' registered successfully",
                server_name=request.name
            )
        else:
            error_msg = f"OpenCode API returned status {response.status_code}: {response.text}"
            logger.error(
                f"❌ MCP registration failed",
                extra={
                    "server_name": request.name,
                    "status_code": response.status_code,
                    "response": response.text
                }
            )
            
            raise HTTPException(
                status_code=response.status_code,
                detail=error_msg
            )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(
            f"❌ Failed to register MCP server '{request.name}': {e}",
            extra={
                "server_name": request.name,
                "error_type": type(e).__name__,
                "error": str(e)
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register MCP server: {str(e)}"
        )
    
    finally:
        await opencode.close()


@router.get("/status")
async def get_mcp_status() -> dict[str, Any]:
    """
    Get status of all registered MCP servers
    
    Queries OpenCode to retrieve the current status of all MCP servers.
    
    **Returns:**
    Dictionary mapping server names to their status information.
    
    **Example Response:**
    ```json
    {
        "my-mcp-server": {
            "status": "connected",
            "tools_count": 25
        }
    }
    ```
    """
    logger.info("📊 Fetching MCP status from OpenCode")
    
    opencode = OpenCodeClient(base_url=settings.opencode_base_url)
    
    try:
        mcp_status = await opencode.get_mcp_status()
        
        logger.info(
            f"✅ Retrieved MCP status",
            extra={
                "servers": list(mcp_status.keys()),
                "count": len(mcp_status)
            }
        )
        
        return mcp_status
    
    except Exception as e:
        logger.error(
            f"❌ Failed to get MCP status: {e}",
            exc_info=True
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get MCP status: {str(e)}"
        )
    
    finally:
        await opencode.close()


@router.get("/tools")
async def list_mcp_tools() -> dict[str, Any]:
    """
    List all available MCP tools
    
    Retrieves a list of all available MCP tools from OpenCode.
    
    **Returns:**
    Dictionary of available tool IDs and their information.
    """
    logger.info("🔍 Listing MCP tools from OpenCode")
    
    opencode = OpenCodeClient(base_url=settings.opencode_base_url)
    
    try:
        tools = await opencode.list_mcp_tools()
        
        logger.info(
            f"✅ Retrieved MCP tools list",
            extra={"tools_count": len(tools) if tools else 0}
        )
        
        return tools
    
    except Exception as e:
        logger.error(
            f"❌ Failed to list MCP tools: {e}",
            exc_info=True
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list MCP tools: {str(e)}"
        )
    
    finally:
        await opencode.close()

