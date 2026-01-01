"""
Global error handling middleware
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from reasoner_pod.utils.logging import get_logger, correlation_id_var

logger = get_logger(__name__)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle HTTP exceptions"""
    correlation_id = correlation_id_var.get('')
    
    logger.warning(
        f"HTTP {exc.status_code}: {exc.detail}",
        extra={
            "path": str(request.url),
            "method": request.method,
            "status_code": exc.status_code,
            "correlation_id": correlation_id
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "http_error",
                "message": exc.detail,
                "status_code": exc.status_code,
                "correlation_id": correlation_id
            }
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors"""
    correlation_id = correlation_id_var.get('')
    
    logger.warning(
        f"Validation error: {exc.errors()}",
        extra={
            "path": str(request.url),
            "method": request.method,
            "validation_errors": exc.errors(),
            "correlation_id": correlation_id
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "type": "validation_error",
                "message": "Request validation failed",
                "details": exc.errors(),
                "correlation_id": correlation_id
            }
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions"""
    correlation_id = correlation_id_var.get('')
    
    logger.exception(
        f"Unhandled exception: {str(exc)}",
        extra={
            "path": str(request.url),
            "method": request.method,
            "correlation_id": correlation_id
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "type": "internal_error",
                "message": "An unexpected error occurred",
                "correlation_id": correlation_id
            }
        }
    )


