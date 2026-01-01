"""
Dependency injection for FastAPI
"""
from typing import Annotated
from fastapi import Depends, Header

from reasoner_pod.config import settings
from reasoner_pod.core.job_store import JobStore
from reasoner_pod.clients.opencode import OpenCodeClient


# Singleton instances
_job_store: JobStore | None = None
_opencode_client: OpenCodeClient | None = None


def get_job_store() -> JobStore:
    """Get JobStore singleton"""
    global _job_store
    if _job_store is None:
        _job_store = JobStore(checkpoint_dir=settings.checkpoint_dir)
    return _job_store


def get_opencode_client() -> OpenCodeClient:
    """Get OpenCodeClient singleton"""
    global _opencode_client
    if _opencode_client is None:
        _opencode_client = OpenCodeClient(
            base_url=settings.opencode_base_url,
            timeout=settings.opencode_timeout
        )
    return _opencode_client


def get_correlation_id(
    x_correlation_id: Annotated[str | None, Header()] = None
) -> str:
    """Get or generate correlation ID for request tracing"""
    import uuid
    return x_correlation_id or str(uuid.uuid4())


# Type aliases for dependency injection
JobStoreDep = Annotated[JobStore, Depends(get_job_store)]
OpenCodeClientDep = Annotated[OpenCodeClient, Depends(get_opencode_client)]
CorrelationIdDep = Annotated[str, Depends(get_correlation_id)]


