"""
Main FastAPI application for Reasoner Pod
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from reasoner_pod import __version__
from reasoner_pod.config import settings
from reasoner_pod.api.routes import jobs, health, mcp
from reasoner_pod.middleware.logging import RequestLoggingMiddleware
from reasoner_pod.middleware.metrics import MetricsMiddleware
from reasoner_pod.middleware.error_handler import (
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler
)
from reasoner_pod.utils.logging import setup_logging, get_logger
from reasoner_pod.utils.metrics import metrics
from reasoner_pod.dependencies import get_job_store

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler
    
    Handles startup and shutdown events
    """
    # Startup
    logger.info(
        f"Starting Reasoner Pod v{__version__}",
        extra={
            "version": __version__,
            "environment": settings.environment,
            "opencode_url": settings.opencode_base_url
        }
    )
    
    # Clear old checkpoints (fresh start with new architecture)
    from pathlib import Path
    checkpoint_dir = Path(settings.checkpoint_dir)
    if checkpoint_dir.exists():
        checkpoint_count = len(list(checkpoint_dir.glob("*.json")))
        if checkpoint_count > 0:
            logger.info(f"🧹 Clearing {checkpoint_count} old checkpoints for fresh start")
            for checkpoint_file in checkpoint_dir.glob("*.json"):
                try:
                    checkpoint_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete checkpoint {checkpoint_file}: {e}")
    
    # Initialize job store
    job_store = get_job_store()
    logger.info(f"JobStore initialized (empty, fresh start)")
    
    # Update metrics
    metrics.set_active_jobs(0)
    
    # Check OpenCode connectivity (MCP registration is now handled via API endpoint)
    from reasoner_pod.clients.opencode import OpenCodeClient
    opencode = OpenCodeClient(base_url=settings.opencode_base_url)
    
    try:
        logger.info("🔍 Checking OpenCode connectivity...")
        is_healthy = await opencode.health_check()
        
        if not is_healthy:
            logger.warning(
                "⚠️ OpenCode server is not healthy. Jobs may fail.",
                extra={
                    "action_required": "Check OpenCode service availability"
                }
            )
        else:
            logger.info("✅ OpenCode server is healthy")
        
        logger.info(
            "ℹ️ MCP registration is now handled via API. Use POST /mcp/register to register MCP servers.",
            extra={
                "endpoint": "/mcp/register",
                "method": "POST"
            }
        )
    
    except Exception as e:
        logger.warning(
            f"⚠️ OpenCode health check failed: {e}",
            extra={
                "error": str(e),
                "impact": "Jobs may fail if OpenCode is unavailable"
            }
        )
        # Don't crash the app - OpenCode might become available later
    
    finally:
        await opencode.close()
    
    logger.info("🚀 Reasoner Pod is ready to accept jobs")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Reasoner Pod")
    
    # Save any active job checkpoints
    active_jobs = await job_store.get_active_jobs()
    for job in active_jobs:
        await job_store.save_checkpoint(job)
    
    logger.info(f"Saved checkpoints for {len(active_jobs)} active jobs")


# Create FastAPI application
app = FastAPI(
    title="Reasoner Pod",
    description="Production AI Reasoner with OpenCode Integration",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None
)

# Add middleware (order matters - last added is executed first)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# Register exception handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(mcp.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Reasoner Pod",
        "version": __version__,
        "environment": settings.environment,
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "reasoner_pod.main:app",
        host=settings.reasoner_pod_host,
        port=settings.reasoner_pod_port,
        reload=settings.is_development
    )


