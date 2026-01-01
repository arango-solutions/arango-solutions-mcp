"""
Job API schemas
"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from reasoner_pod.core.models import JobStatus, JobStep


class JobCreateRequest(BaseModel):
    """Request model for creating a job"""
    request: str = Field(description="User's natural language request", min_length=1)
    context: Optional[dict[str, Any]] = Field(default=None, description="Additional context for the request")
    
    class Config:
        json_schema_extra = {
            "example": {
                "request": "Find all users in ArangoDB where age > 25 and optimize the query",
                "context": {"database": "users_db"}
            }
        }


class JobResponse(BaseModel):
    """Response model for job creation"""
    job_id: str = Field(description="Unique job identifier")
    status: JobStatus = Field(description="Current job status")
    message: str = Field(description="Human-readable message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "message": "Job created and queued for processing"
            }
        }


class JobStatusResponse(BaseModel):
    """Response model for job status queries"""
    job_id: str
    status: JobStatus
    user_request: str
    plan: Optional[list[str]] = None
    steps: list[JobStep] = []
    current_step: int = 0
    final_result: Optional[str] = None
    error: Optional[str] = None
    context: Optional[dict[str, Any]] = None  # Include for debugging
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    progress_percentage: float = 0.0
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "executing",
                "user_request": "Find all users in ArangoDB where age > 25",
                "plan": [
                    "Connect to ArangoDB",
                    "Execute AQL query",
                    "Return results"
                ],
                "steps": [
                    {
                        "step_num": 1,
                        "description": "Execute AQL query",
                        "tool_used": "db_query_aql",
                        "result": "Query executed successfully",
                        "duration_ms": 150
                    }
                ],
                "current_step": 1,
                "progress_percentage": 33.33,
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:00:05Z"
            }
        }


