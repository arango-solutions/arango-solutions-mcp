"""
Structured logging configuration
"""
import logging
import sys
from datetime import datetime
from pythonjsonlogger import jsonlogger
from reasoner_pod.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""
    
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # Add timestamp
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        
        # Add service name
        log_record['service'] = 'reasoner-pod'
        
        # Add environment
        log_record['environment'] = settings.environment
        
        # Add log level
        log_record['level'] = record.levelname
        
        # Ensure message field exists
        if 'message' not in log_record:
            log_record['message'] = record.getMessage()


def setup_logging() -> None:
    """Configure logging for the application"""
    
    # Determine format based on configuration
    if settings.log_format == "json":
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
    else:
        # Text format for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    root_logger.info(
        f"Logging configured: level={settings.log_level}, format={settings.log_format}"
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Context variables for request-scoped logging
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')
job_id_var: ContextVar[str] = ContextVar('job_id', default='')


class ContextLogger:
    """Logger wrapper that includes context variables"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def _get_extra(self, extra: dict | None = None) -> dict:
        """Build extra dict with context variables"""
        context_extra = {}
        
        correlation_id = correlation_id_var.get()
        if correlation_id:
            context_extra['correlation_id'] = correlation_id
        
        job_id = job_id_var.get()
        if job_id:
            context_extra['job_id'] = job_id
        
        if extra:
            context_extra.update(extra)
        
        return context_extra
    
    def debug(self, msg, *args, **kwargs):
        extra = self._get_extra(kwargs.pop('extra', None))
        self.logger.debug(msg, *args, extra=extra, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        extra = self._get_extra(kwargs.pop('extra', None))
        self.logger.info(msg, *args, extra=extra, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        extra = self._get_extra(kwargs.pop('extra', None))
        self.logger.warning(msg, *args, extra=extra, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        extra = self._get_extra(kwargs.pop('extra', None))
        self.logger.error(msg, *args, extra=extra, **kwargs)
    
    def critical(self, msg, *args, **kwargs):
        extra = self._get_extra(kwargs.pop('extra', None))
        self.logger.critical(msg, *args, extra=extra, **kwargs)
    
    def exception(self, msg, *args, **kwargs):
        extra = self._get_extra(kwargs.pop('extra', None))
        self.logger.exception(msg, *args, extra=extra, **kwargs)


def get_context_logger(name: str) -> ContextLogger:
    """
    Get a context-aware logger
    
    Args:
        name: Logger name
        
    Returns:
        Context-aware logger
    """
    return ContextLogger(logging.getLogger(name))


