"""
Health check and monitoring endpoints
"""
from fastapi import APIRouter, Response, Depends
import httpx
from reasoner_pod import __version__
from reasoner_pod.config import settings
from reasoner_pod.api.schemas.health import HealthResponse, ReadinessResponse, StatsResponse
from reasoner_pod.dependencies import JobStoreDep
from reasoner_pod.utils.docker import DockerHelper
from reasoner_pod.utils.metrics import get_metrics

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint (liveness probe)
    
    Returns:
        Health status of the service
    """
    return HealthResponse(
        status="healthy",
        version=__version__,
        environment=settings.environment
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check():
    """
    Readiness check endpoint - validates all dependencies
    
    Returns:
        Readiness status with dependency checks
    """
    checks = {}
    all_ready = True
    
    # Check OpenCode connectivity
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.opencode_base_url}/global/health")
            opencode_healthy = response.status_code == 200
    except Exception as e:
        opencode_healthy = False
        
    checks["opencode"] = {
        "status": "healthy" if opencode_healthy else "unhealthy",
        "url": settings.opencode_base_url
    }
    all_ready = all_ready and opencode_healthy
    
    # Check MCP servers via OpenCode (optional - any registered MCP servers)
    mcp_available = False
    mcp_details = {}
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.opencode_base_url}/mcp")
            if response.status_code == 200:
                mcp_status = response.json()
                mcp_details = mcp_status
                # Check if any MCP servers are connected
                connected_servers = [
                    name for name, info in mcp_status.items()
                    if info.get("status") == "connected"
                ]
                mcp_available = len(connected_servers) > 0
    except Exception as e:
        # MCP is optional, don't block readiness
        pass
    
    checks["mcp_servers"] = {
        "status": "available" if mcp_available else "none",
        "details": mcp_details
    }
    # Don't block readiness on MCP - it's optional
    # all_ready = all_ready and mcp_available
    
    return ReadinessResponse(
        ready=all_ready,
        checks=checks
    )


@router.get("/health/stats", response_model=StatsResponse)
async def get_stats(job_store: JobStoreDep):
    """
    Get job statistics
    
    Args:
        job_store: Job store dependency
        
    Returns:
        Job statistics
    """
    stats = await job_store.get_stats()
    return StatsResponse(**stats)


@router.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint
    
    Returns:
        Metrics in Prometheus text format
    """
    metrics_content, content_type = get_metrics()
    return Response(content=metrics_content, media_type=content_type)


@router.get("/health/mcp")
async def mcp_health_check():
    """
    MCP connectivity health check via OpenCode
    
    Checks MCP server status through OpenCode's /mcp endpoint.
    This shows which MCP servers are registered and their connection status.
    
    Returns:
        Health status for each registered MCP server including:
        - status: Overall health ("healthy", "degraded", "unhealthy", "error")
        - servers: Dictionary of server statuses
        - source: "opencode" (indicates this is from OpenCode's MCP management)
        - expected_servers: List of servers we expect to be registered
        - timestamp: ISO 8601 timestamp
    """
    from datetime import datetime
    from reasoner_pod.utils.logging import get_logger
    
    logger = get_logger(__name__)
    expected_servers = []  # No specific MCP servers required
    
    try:
        logger.info(
            "🔍 Checking MCP server health via OpenCode",
            extra={
                "endpoint": f"{settings.opencode_base_url}/mcp",
                "expected_servers": expected_servers
            }
        )
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.opencode_base_url}/mcp")
            
            if response.status_code == 200:
                mcp_status = response.json()
                
                logger.info(
                    "📊 Received MCP status from OpenCode",
                    extra={
                        "registered_servers": list(mcp_status.keys()),
                        "server_count": len(mcp_status)
                    }
                )
                
                # Determine overall health
                connected_servers = [
                    name for name, info in mcp_status.items()
                    if info.get("status") == "connected"
                ]
                
                all_healthy = all(
                    server.get("status") == "connected" 
                    for server in mcp_status.values()
                )
                
                # Check if expected servers are registered
                missing_servers = [s for s in expected_servers if s not in mcp_status]
                
                health_status = "healthy" if all_healthy and not missing_servers else "degraded"
                
                logger.info(
                    f"✅ MCP health check complete: {health_status}",
                    extra={
                        "status": health_status,
                        "connected_servers": connected_servers,
                        "missing_servers": missing_servers,
                        "all_healthy": all_healthy
                    }
                )
                
                return {
                    "status": health_status,
                    "servers": mcp_status,
                    "connected_servers": connected_servers,
                    "expected_servers": expected_servers,
                    "missing_servers": missing_servers,
                    "source": "opencode",
                    "opencode_url": settings.opencode_base_url,
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                logger.error(
                    f"❌ OpenCode MCP endpoint returned error",
                    extra={
                        "status_code": response.status_code,
                        "response_text": response.text[:200]
                    }
                )
                return {
                    "status": "unhealthy",
                    "error": f"OpenCode MCP endpoint returned {response.status_code}",
                    "expected_servers": expected_servers,
                    "source": "opencode",
                    "opencode_url": settings.opencode_base_url,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
    except Exception as e:
        logger.error(
            f"❌ MCP health check failed",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e)
            },
            exc_info=True
        )
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "expected_servers": expected_servers,
            "source": "opencode",
            "opencode_url": settings.opencode_base_url,
            "timestamp": datetime.utcnow().isoformat()
        }


