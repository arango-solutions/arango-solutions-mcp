"""Bounded-cardinality Prometheus metrics for MCP operations."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram

_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 120)
_AQL_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30)
_LOCK = threading.Lock()


@dataclass(frozen=True)
class MetricSuite:
    tool_calls: Counter
    tool_duration: Histogram
    tool_errors: Counter
    aql_runtime: Histogram
    dependency_calls: Counter
    dependency_duration: Histogram
    dependency_inflight: Gauge
    limiter_inflight: Gauge
    limiter_rejections: Counter
    rate_limit_remaining: Gauge


def _build(registry: CollectorRegistry) -> MetricSuite:
    return MetricSuite(
        tool_calls=Counter(
            "mcp_tool_calls_total",
            "MCP tool calls by catalog identity and outcome.",
            ("tool", "operation", "outcome"),
            registry=registry,
        ),
        tool_duration=Histogram(
            "mcp_tool_duration_seconds",
            "MCP tool duration.",
            ("tool", "operation", "outcome"),
            buckets=_DURATION_BUCKETS,
            registry=registry,
        ),
        tool_errors=Counter(
            "mcp_tool_errors_total",
            "MCP tool errors without unbounded error labels.",
            ("tool", "operation"),
            registry=registry,
        ),
        aql_runtime=Histogram(
            "mcp_aql_runtime_seconds",
            "AQL driver execution runtime.",
            ("operation", "outcome"),
            buckets=_AQL_BUCKETS,
            registry=registry,
        ),
        dependency_calls=Counter(
            "mcp_dependency_calls_total",
            "ArangoDB and embedding dependency calls.",
            ("dependency", "operation", "outcome"),
            registry=registry,
        ),
        dependency_duration=Histogram(
            "mcp_dependency_duration_seconds",
            "Dependency call duration.",
            ("dependency", "operation", "outcome"),
            buckets=_DURATION_BUCKETS,
            registry=registry,
        ),
        dependency_inflight=Gauge(
            "mcp_dependency_inflight",
            "Current dependency calls, exposing driver/provider pressure.",
            ("dependency", "operation"),
            registry=registry,
        ),
        limiter_inflight=Gauge(
            "mcp_limiter_inflight",
            "Current accepted work by bounded limiter scope.",
            ("scope", "limit_class"),
            registry=registry,
        ),
        limiter_rejections=Counter(
            "mcp_limiter_rejections_total",
            "Rejected work by limiter scope and reason.",
            ("scope", "limit_class", "reason"),
            registry=registry,
        ),
        rate_limit_remaining=Gauge(
            "mcp_rate_limit_remaining",
            "Aggregate minimum remaining actor tokens; actor IDs are never labels.",
            registry=registry,
        ),
    )


_registry: CollectorRegistry = REGISTRY
_metrics = _build(_registry)


def configure_metrics_registry(registry: CollectorRegistry) -> MetricSuite:
    """Replace the active suite, primarily for deterministic isolated tests."""
    global _metrics, _registry
    with _LOCK:
        _registry = registry
        _metrics = _build(registry)
        return _metrics


def get_registry() -> CollectorRegistry:
    return _registry


def observe_tool(tool: str, operation: str, outcome: str, duration: float) -> None:
    suite = _metrics
    suite.tool_calls.labels(tool, operation, outcome).inc()
    suite.tool_duration.labels(tool, operation, outcome).observe(duration)
    if outcome == "error":
        suite.tool_errors.labels(tool, operation).inc()


def dependency_started(dependency: str, operation: str) -> None:
    _metrics.dependency_inflight.labels(dependency, operation).inc()


def dependency_finished(dependency: str, operation: str, outcome: str, duration: float) -> None:
    suite = _metrics
    suite.dependency_inflight.labels(dependency, operation).dec()
    suite.dependency_calls.labels(dependency, operation, outcome).inc()
    suite.dependency_duration.labels(dependency, operation, outcome).observe(duration)


def observe_aql(operation: str, outcome: str, duration: float) -> None:
    _metrics.aql_runtime.labels(operation, outcome).observe(duration)


def limiter_inflight(scope: str, limit_class: str, delta: int) -> None:
    _metrics.limiter_inflight.labels(scope, limit_class).inc(delta)


def limiter_rejected(scope: str, limit_class: str, reason: str) -> None:
    _metrics.limiter_rejections.labels(scope, limit_class, reason).inc()


def set_rate_limit_remaining(value: float) -> None:
    _metrics.rate_limit_remaining.set(max(0.0, value))


def metric_names() -> frozenset[str]:
    """Expose the fixed collector inventory for static contract tests."""
    return frozenset(
        {
            "mcp_tool_calls_total",
            "mcp_tool_duration_seconds",
            "mcp_tool_errors_total",
            "mcp_aql_runtime_seconds",
            "mcp_dependency_calls_total",
            "mcp_dependency_duration_seconds",
            "mcp_dependency_inflight",
            "mcp_limiter_inflight",
            "mcp_limiter_rejections_total",
            "mcp_rate_limit_remaining",
        }
    )
