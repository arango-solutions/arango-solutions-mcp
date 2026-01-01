"""
Metrics collection middleware
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting application metrics"""
    
    async def dispatch(self, request: Request, call_next):
        # Currently metrics are handled in RequestLoggingMiddleware
        # This middleware is reserved for future metrics-specific logic
        response = await call_next(request)
        return response


