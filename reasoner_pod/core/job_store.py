"""
Job storage with in-memory caching and file-based checkpointing
"""
import json
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime

from reasoner_pod.core.models import Job, JobStatus, JobCheckpoint
from reasoner_pod.utils.logging import get_logger

logger = get_logger(__name__)


class JobStore:
    """
    In-memory job storage with file-based checkpointing for persistence
    """
    
    def __init__(self, checkpoint_dir: str = "/app/data/checkpoints"):
        """
        Initialize job store
        
        Args:
            checkpoint_dir: Directory for checkpoint files
        """
        self.jobs: dict[str, Job] = {}
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        
        logger.info(f"JobStore initialized with checkpoint_dir={checkpoint_dir}")
        
        # Load existing checkpoints on startup
        self._load_checkpoints()
    
    def _load_checkpoints(self) -> None:
        """Load existing checkpoints from disk"""
        try:
            checkpoint_files = list(self.checkpoint_dir.glob("*.json"))
            loaded_count = 0
            
            for checkpoint_file in checkpoint_files:
                try:
                    with open(checkpoint_file, 'r') as f:
                        data = json.load(f)
                        checkpoint = JobCheckpoint(**data)
                        job = checkpoint.job
                        
                        # Only load non-terminal jobs
                        if not job.is_terminal:
                            self.jobs[job.job_id] = job
                            loaded_count += 1
                            logger.debug(f"Loaded checkpoint for job {job.job_id}")
                        
                except Exception as e:
                    logger.error(f"Failed to load checkpoint {checkpoint_file}: {e}")
            
            if loaded_count > 0:
                logger.info(f"Loaded {loaded_count} job checkpoints from disk")
        
        except Exception as e:
            logger.error(f"Error loading checkpoints: {e}")
    
    async def create_job(self, job: Job) -> Job:
        """
        Create a new job
        
        Args:
            job: Job to create
            
        Returns:
            Created job
        """
        async with self._lock:
            if job.job_id in self.jobs:
                raise ValueError(f"Job {job.job_id} already exists")
            
            self.jobs[job.job_id] = job
            logger.info(f"Created job {job.job_id}", extra={"job_id": job.job_id})
            
            # Save initial checkpoint
            await self._save_checkpoint(job)
            
            return job
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job if found, None otherwise
        """
        return self.jobs.get(job_id)
    
    async def update_job(self, job: Job) -> Job:
        """
        Update existing job
        
        Args:
            job: Job to update
            
        Returns:
            Updated job
        """
        async with self._lock:
            if job.job_id not in self.jobs:
                raise ValueError(f"Job {job.job_id} not found")
            
            job.updated_at = datetime.utcnow()
            self.jobs[job.job_id] = job
            
            logger.debug(f"Updated job {job.job_id}", extra={
                "job_id": job.job_id,
                "status": job.status.value
            })
            
            return job
    
    async def save_checkpoint(self, job: Job) -> None:
        """
        Save job checkpoint to disk
        
        Args:
            job: Job to checkpoint
        """
        await self._save_checkpoint(job)
    
    async def _save_checkpoint(self, job: Job) -> None:
        """Internal checkpoint save implementation"""
        try:
            checkpoint = JobCheckpoint(job=job)
            checkpoint_file = self.checkpoint_dir / f"{job.job_id}.json"
            
            # Write atomically using temp file
            temp_file = checkpoint_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                f.write(checkpoint.model_dump_json(indent=2))
            
            temp_file.rename(checkpoint_file)
            
            logger.debug(f"Saved checkpoint for job {job.job_id}")
        
        except Exception as e:
            logger.error(f"Failed to save checkpoint for job {job.job_id}: {e}", extra={
                "job_id": job.job_id,
                "error": str(e)
            })
    
    async def delete_checkpoint(self, job_id: str) -> None:
        """
        Delete job checkpoint from disk
        
        Args:
            job_id: Job identifier
        """
        try:
            checkpoint_file = self.checkpoint_dir / f"{job_id}.json"
            if checkpoint_file.exists():
                checkpoint_file.unlink()
                logger.debug(f"Deleted checkpoint for job {job_id}")
        
        except Exception as e:
            logger.error(f"Failed to delete checkpoint for job {job_id}: {e}")
    
    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[Job]:
        """
        List jobs with optional filtering
        
        Args:
            status: Filter by job status
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            
        Returns:
            List of jobs
        """
        jobs = list(self.jobs.values())
        
        # Filter by status if provided
        if status:
            jobs = [job for job in jobs if job.status == status]
        
        # Sort by creation time (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        # Apply pagination
        return jobs[offset:offset + limit]
    
    async def get_pending_jobs(self) -> list[Job]:
        """
        Get all pending jobs
        
        Returns:
            List of pending jobs
        """
        return [job for job in self.jobs.values() if job.status == JobStatus.PENDING]
    
    async def get_active_jobs(self) -> list[Job]:
        """
        Get all active (non-terminal) jobs
        
        Returns:
            List of active jobs
        """
        return [job for job in self.jobs.values() if not job.is_terminal]
    
    async def get_stats(self) -> dict:
        """
        Get job store statistics
        
        Returns:
            Dictionary with job statistics
        """
        jobs = list(self.jobs.values())
        
        return {
            "total_jobs": len(jobs),
            "pending": len([j for j in jobs if j.status == JobStatus.PENDING]),
            "planning": len([j for j in jobs if j.status == JobStatus.PLANNING]),
            "executing": len([j for j in jobs if j.status == JobStatus.EXECUTING]),
            "completed": len([j for j in jobs if j.status == JobStatus.COMPLETED]),
            "failed": len([j for j in jobs if j.status == JobStatus.FAILED]),
            "cancelled": len([j for j in jobs if j.status == JobStatus.CANCELLED]),
            "active": len([j for j in jobs if not j.is_terminal])
        }
    
    def __len__(self) -> int:
        """Get number of jobs in store"""
        return len(self.jobs)


