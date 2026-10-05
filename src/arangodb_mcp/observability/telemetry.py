"""OpenTelemetry bootstrap with OTLP/HTTP export."""

from __future__ import annotations

import threading
from typing import Any
from urllib.parse import unquote

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from arangodb_mcp.observability.conventions import CONVENTION_VERSION

_LOCK = threading.Lock()
_CONFIGURED = False
_tracer_provider_override: trace.TracerProvider | None = None


def get_tracer() -> trace.Tracer:
    """Return the tracer used by every operations span."""
    provider = _tracer_provider_override
    if provider is not None:
        return provider.get_tracer("arangodb-mcp-server", CONVENTION_VERSION)
    return trace.get_tracer("arangodb-mcp-server", CONVENTION_VERSION)


def set_tracer_provider_for_testing(provider: trace.TracerProvider | None) -> None:
    """Inject an isolated provider without mutating OpenTelemetry global state."""
    global _tracer_provider_override
    _tracer_provider_override = provider


def configure_telemetry(config: Any) -> bool:
    """Configure one process-wide OTLP/HTTP provider when explicitly enabled."""
    global _CONFIGURED
    if config.otel_traces_exporter == "none":
        return False
    with _LOCK:
        if _CONFIGURED:
            return True
        endpoint = config.otel_exporter_otlp_endpoint.rstrip("/")
        if not endpoint.endswith("/v1/traces"):
            endpoint += "/v1/traces"
        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": config.otel_service_name,
                    "service.version": config.otel_service_version,
                    "telemetry.sdk.language": "python",
                }
            )
        )
        exporter = OTLPSpanExporter(
            endpoint=endpoint,
            headers=_parse_headers(config.otel_exporter_otlp_headers.get_secret_value()),
            timeout=config.otel_exporter_otlp_timeout_seconds,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _CONFIGURED = True
        return True


def _parse_headers(raw: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in raw.split(","):
        if not item.strip():
            continue
        key, separator, value = item.partition("=")
        if separator and key.strip():
            headers[key.strip()] = unquote(value.strip())
    return headers
