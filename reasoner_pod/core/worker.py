"""
Background worker for asynchronous job processing
"""
from reasoner_pod.core.job_store import JobStore
from reasoner_pod.clients.opencode import OpenCodeClient
from reasoner_pod.agents.reasoner import ReasonerAgent
from reasoner_pod.config import settings
from reasoner_pod.utils.logging import get_logger
from reasoner_pod.utils.metrics import metrics

logger = get_logger(__name__)


async def process_job_async(job_id: str) -> None:
    """
    Process a job asynchronously in the background
    
    Args:
        job_id: Job identifier to process
    """
    logger.info(f"Background processing started for job {job_id}")
    
    # Get dependencies
    from reasoner_pod.dependencies import get_job_store, get_opencode_client
    
    job_store = get_job_store()
    opencode_client = get_opencode_client()
    
    try:
        # Get job from store
        job = await job_store.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found in store")
            return
        
        # Create reasoner agent
        reasoner = ReasonerAgent(opencode_client)
        
        # Process job
        updated_job = await reasoner.process_job(job)
        
        # Update job in store
        await job_store.update_job(updated_job)
        
        # Save final checkpoint
        await job_store.save_checkpoint(updated_job)
        
        # Update metrics
        active_jobs = await job_store.get_active_jobs()
        metrics.set_active_jobs(len(active_jobs))
        
        logger.info(f"Background processing completed for job {job_id}")
    
    except Exception as e:
        logger.error(f"Background processing failed for job {job_id}: {e}", exc_info=True)
        
        # Try to update job with error
        try:
            job = await job_store.get_job(job_id)
            if job:
                from reasoner_pod.core.models import JobStatus
                job.update_status(JobStatus.FAILED)
                job.error = str(e)
                await job_store.update_job(job)
                await job_store.save_checkpoint(job)
        except Exception as update_error:
            logger.error(f"Failed to update job with error: {update_error}")


