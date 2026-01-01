"""
Request logging middleware
"""
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from reasoner_pod.utils.logging import get_logger, correlation_id_var
from reasoner_pod.utils.metrics import metrics

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate or extract correlation ID
        correlation_id = request.headers.get('x-correlation-id', '')
        if not correlation_id:
            import uuid
            correlation_id = str(uuid.uuid4())
        
        # Set correlation ID in context
        correlation_id_var.set(correlation_id)
        
        # Start timer
        start_time = time.time()
        
        # Log request
        logger.info(
            f"{request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "correlation_id": correlation_id,
                "client_host": request.client.host if request.client else None
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            metrics.record_api_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                duration=duration
            )
            
            # Log response
            logger.info(
                f"{request.method} {request.url.path} - {response.status_code}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "correlation_id": correlation_id
                }
            )
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
        
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            logger.error(
                f"{request.method} {request.url.path} - Error: {str(e)}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration * 1000, 2),
                    "correlation_id": correlation_id,
                    "error": str(e)
                }
            )
            raise


