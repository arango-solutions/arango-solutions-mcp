"""
Prometheus metrics for monitoring
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from reasoner_pod.core.models import JobStatus


# Job metrics
job_total = Counter(
    'reasoner_jobs_total',
    'Total number of jobs created',
    ['status']
)

job_duration_seconds = Histogram(
    'reasoner_jobs_duration_seconds',
    'Job processing duration in seconds',
    ['status'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
)

job_active = Gauge(
    'reasoner_jobs_active',
    'Number of currently active jobs'
)

job_steps_total = Counter(
    'reasoner_job_steps_total',
    'Total number of job steps executed'
)

# API metrics
api_requests_total = Counter(
    'reasoner_api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status_code']
)

api_request_duration_seconds = Histogram(
    'reasoner_api_request_duration_seconds',
    'API request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
)

# OpenCode metrics
opencode_requests_total = Counter(
    'reasoner_opencode_requests_total',
    'Total number of OpenCode API requests',
    ['operation', 'status']
)

opencode_request_duration_seconds = Histogram(
    'reasoner_opencode_request_duration_seconds',
    'OpenCode request duration in seconds',
    ['operation'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120]
)

# MCP metrics
mcp_tool_calls_total = Counter(
    'reasoner_mcp_tool_calls_total',
    'Total number of MCP tool calls',
    ['tool_name', 'status']
)

mcp_tool_duration_seconds = Histogram(
    'reasoner_mcp_tool_duration_seconds',
    'MCP tool execution duration in seconds',
    ['tool_name'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10, 30]
)


class MetricsCollector:
    """Helper class for collecting metrics"""
    
    @staticmethod
    def record_job_created(status: JobStatus = JobStatus.PENDING):
        """Record job creation"""
        job_total.labels(status=status.value).inc()
    
    @staticmethod
    def record_job_completed(status: JobStatus, duration_seconds: float):
        """Record job completion"""
        job_duration_seconds.labels(status=status.value).observe(duration_seconds)
        job_total.labels(status=status.value).inc()
    
    @staticmethod
    def set_active_jobs(count: int):
        """Set number of active jobs"""
        job_active.set(count)
    
    @staticmethod
    def record_job_step():
        """Record job step execution"""
        job_steps_total.inc()
    
    @staticmethod
    def record_api_request(method: str, endpoint: str, status_code: int, duration: float):
        """Record API request"""
        api_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code
        ).inc()
        api_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    @staticmethod
    def record_opencode_request(operation: str, status: str, duration: float):
        """Record OpenCode request"""
        opencode_requests_total.labels(
            operation=operation,
            status=status
        ).inc()
        opencode_request_duration_seconds.labels(
            operation=operation
        ).observe(duration)
    
    @staticmethod
    def record_mcp_tool_call(tool_name: str, status: str, duration: float):
        """Record MCP tool call"""
        mcp_tool_calls_total.labels(
            tool_name=tool_name,
            status=status
        ).inc()
        mcp_tool_duration_seconds.labels(
            tool_name=tool_name
        ).observe(duration)


def get_metrics() -> tuple[bytes, str]:
    """
    Get Prometheus metrics in text format
    
    Returns:
        Tuple of (metrics_content, content_type)
    """
    return generate_latest(), CONTENT_TYPE_LATEST


# Global metrics collector instance
metrics = MetricsCollector()


