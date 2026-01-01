"""
Core domain models for the Reasoner Pod
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


class JobStatus(str, Enum):
    """Job execution status"""
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStep(BaseModel):
    """Individual step in job execution"""
    step_num: int = Field(description="Step number in execution sequence")
    description: str = Field(description="Human-readable step description")
    tool_used: Optional[str] = Field(default=None, description="Name of tool/MCP server used")
    tool_input: Optional[dict[str, Any]] = Field(default=None, description="Input parameters for tool")
    result: Optional[Any] = Field(default=None, description="Step execution result (can be string, dict, list, etc.)")
    duration_ms: float = Field(default=0.0, description="Execution duration in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Step execution timestamp")
    error: Optional[str] = Field(default=None, description="Error message if step failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "step_num": 1,
                "description": "Query users from ArangoDB",
                "tool_used": "db_query_aql",
                "tool_input": {"query": "FOR doc IN users FILTER doc.age > 25 RETURN doc"},
                "result": "Found 42 users",
                "duration_ms": 150,
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }


class Job(BaseModel):
    """Job representing a reasoning task"""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique job identifier")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Current job status")
    user_request: str = Field(description="Original user request/query")
    context: Optional[dict[str, Any]] = Field(default=None, description="Additional context for the job")
    
    # Planning phase
    plan: Optional[list[str]] = Field(default=None, description="Step-by-step execution plan")
    
    # Execution phase
    steps: list[JobStep] = Field(default_factory=list, description="Executed steps with results")
    current_step: int = Field(default=0, description="Current step number being executed")
    
    # Results
    final_result: Optional[str] = Field(default=None, description="Final synthesized result")
    error: Optional[str] = Field(default=None, description="Error message if job failed")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Job completion timestamp")
    
    # OpenCode session tracking
    opencode_session_id: Optional[str] = Field(default=None, description="OpenCode session ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "user_request": "Find all users over 25 in ArangoDB",
                "plan": [
                    "Connect to ArangoDB via MCP",
                    "Execute AQL query to filter users",
                    "Format and return results"
                ],
                "steps": [
                    {
                        "step_num": 1,
                        "description": "Execute AQL query",
                        "tool_used": "db_query_aql",
                        "result": "Found 42 users",
                        "duration_ms": 150
                    }
                ],
                "final_result": "Found 42 users matching criteria",
                "created_at": "2024-01-01T12:00:00Z",
                "completed_at": "2024-01-01T12:00:05Z"
            }
        }
    
    def update_status(self, new_status: JobStatus) -> None:
        """Update job status and timestamps"""
        self.status = new_status
        self.updated_at = datetime.utcnow()
        
        if new_status == JobStatus.PLANNING and self.started_at is None:
            self.started_at = datetime.utcnow()
        elif new_status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            self.completed_at = datetime.utcnow()
    
    def add_step(self, step: JobStep) -> None:
        """Add an executed step to the job"""
        self.steps.append(step)
        self.current_step = step.step_num
        self.updated_at = datetime.utcnow()
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate total job duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return None
    
    @property
    def progress_percentage(self) -> float:
        """Calculate job progress as percentage"""
        if not self.plan:
            return 0.0
        if self.status == JobStatus.COMPLETED:
            return 100.0
        return (len(self.steps) / len(self.plan)) * 100 if self.plan else 0.0
    
    @property
    def is_terminal(self) -> bool:
        """Check if job is in a terminal state"""
        return self.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]


class JobCheckpoint(BaseModel):
    """Checkpoint data for job persistence"""
    job: Job
    checkpoint_version: int = 1
    saved_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "job": {"job_id": "123", "status": "executing"},
                "checkpoint_version": 1,
                "saved_at": "2024-01-01T12:00:00Z"
            }
        }


