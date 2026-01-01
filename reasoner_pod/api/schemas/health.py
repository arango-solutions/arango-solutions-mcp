"""
Health check schemas
"""
from pydantic import BaseModel, Field
from typing import Optional


class HealthResponse(BaseModel):
    """Basic health check response"""
    status: str = Field(description="Health status")
    version: str = Field(description="Application version")
    environment: str = Field(description="Environment (development/production)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "environment": "production"
            }
        }


class ReadinessResponse(BaseModel):
    """Readiness check response with dependency status"""
    ready: bool = Field(description="Whether the service is ready to accept requests")
    checks: dict[str, dict] = Field(description="Individual service checks")
    
    class Config:
        json_schema_extra = {
            "example": {
                "ready": True,
                "checks": {
                    "opencode": {
                        "status": "healthy",
                        "url": "http://host.docker.internal:4099"
                    },
                    "mcp_servers": {
                        "status": "healthy",
                        "arangodb-mcp": True,
                        "config-mcp": True
                    }
                }
            }
        }


class StatsResponse(BaseModel):
    """Job statistics response"""
    total_jobs: int
    pending: int
    planning: int
    executing: int
    completed: int
    failed: int
    cancelled: int
    active: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_jobs": 150,
                "pending": 5,
                "planning": 2,
                "executing": 3,
                "completed": 135,
                "failed": 4,
                "cancelled": 1,
                "active": 10
            }
        }


