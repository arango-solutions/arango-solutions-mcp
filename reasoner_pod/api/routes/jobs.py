"""
Job management endpoints
"""
from typing import Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
from reasoner_pod.api.schemas.job import JobCreateRequest, JobResponse, JobStatusResponse
from reasoner_pod.core.models import Job, JobStatus
from reasoner_pod.dependencies import JobStoreDep, CorrelationIdDep
from reasoner_pod.utils.logging import get_logger
from reasoner_pod.utils.metrics import metrics

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


from reasoner_pod.core.worker import process_job_async


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    job_store: JobStoreDep,
    correlation_id: CorrelationIdDep
):
    """
    Create a new reasoning job
    
    Args:
        request: Job creation request
        background_tasks: FastAPI background tasks
        job_store: Job store dependency
        correlation_id: Request correlation ID
        
    Returns:
        Job creation response with job_id
    """
    # Create job
    job = Job(
        user_request=request.request,
        context=request.context,
        status=JobStatus.PENDING
    )
    
    # Store job
    await job_store.create_job(job)
    
    # Record metrics
    metrics.record_job_created(JobStatus.PENDING)
    
    logger.info(
        f"Job created: {job.job_id}",
        extra={
            "job_id": job.job_id,
            "correlation_id": correlation_id
        }
    )
    
    # Queue background processing
    background_tasks.add_task(process_job_async, job.job_id)
    
    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        message="Job created and queued for processing"
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    job_store: JobStoreDep,
    correlation_id: CorrelationIdDep
):
    """
    Get job status and results
    
    Args:
        job_id: Job identifier
        job_store: Job store dependency
        correlation_id: Request correlation ID
        
    Returns:
        Job status with details
        
    Raises:
        HTTPException: If job not found
    """
    job = await job_store.get_job(job_id)
    
    if not job:
        logger.warning(
            f"Job not found: {job_id}",
            extra={
                "job_id": job_id,
                "correlation_id": correlation_id
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    logger.debug(
        f"Job status retrieved: {job_id}",
        extra={
            "job_id": job_id,
            "status": job.status.value,
            "correlation_id": correlation_id
        }
    )
    
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        user_request=job.user_request,
        plan=job.plan,
        steps=job.steps,
        current_step=job.current_step,
        final_result=job.final_result,
        error=job.error,
        context=job.context,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        progress_percentage=job.progress_percentage
    )


# Debug endpoints
class DebugOpenCodeRequest(BaseModel):
    """Request model for debug OpenCode endpoint"""
    message: str
    model_provider: str = "openai"
    model_id: str = "gpt-4o"
    
    model_config = {"protected_namespaces": ()}


class DebugOpenCodeResponse(BaseModel):
    """Response model for debug OpenCode endpoint"""
    success: bool
    session_id: str | None = None
    raw_response: dict[str, Any] | None = None
    extracted_text: str | None = None
    error: str | None = None


@router.post("/debug/opencode", response_model=DebugOpenCodeResponse, tags=["Debug"])
async def debug_opencode(request: DebugOpenCodeRequest):
    """
    🔍 DEBUG ENDPOINT: Test OpenCode directly
    
    This endpoint allows you to:
    - Send a message directly to OpenCode
    - See the raw response structure
    - Test different models and prompts
    
    Use this to debug OpenCode integration issues.
    """
    from reasoner_pod.clients.opencode import OpenCodeClient
    from reasoner_pod.config import settings
    
    opencode = None
    session_id = None
    
    try:
        # Initialize OpenCode client (no provider/model in init)
        opencode = OpenCodeClient(base_url=settings.opencode_base_url)
        
        # Create session
        session_id = await opencode.create_session(title="Debug Test")
        logger.info(f"🔍 DEBUG: Created session {session_id}")
        
        # Send message with model configuration
        logger.info(f"🔍 DEBUG: Sending message: {request.message}")
        model_config = {
            "providerID": request.model_provider,
            "modelID": request.model_id
        }
        response = await opencode.send_message(
            content=request.message,
            model=model_config
        )
        
        # Extract text
        parts = response.get("parts", [])
        text_parts = [
            part.get("text", "")
            for part in parts
            if part.get("type") == "text"
        ]
        extracted_text = "\n".join(text_parts)
        
        logger.info(f"🔍 DEBUG: Response parts: {len(parts)}, Extracted text length: {len(extracted_text)}")
        
        return DebugOpenCodeResponse(
            success=True,
            session_id=session_id,
            raw_response=response,
            extracted_text=extracted_text
        )
        
    except Exception as e:
        logger.error(f"🔍 DEBUG: OpenCode test failed: {e}", exc_info=True)
        return DebugOpenCodeResponse(
            success=False,
            session_id=session_id,
            error=str(e)
        )
    
    finally:
        # Cleanup
        if opencode and session_id:
            try:
                await opencode.delete_session(session_id)
                await opencode.close()
            except Exception as e:
                logger.warning(f"🔍 DEBUG: Failed to cleanup: {e}")

