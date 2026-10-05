"""Request-scoped correlation and tracing for HTTP transports."""

from __future__ import annotations

from opentelemetry.propagate import extract
from opentelemetry.trace import Status, StatusCode

from arangodb_mcp.observability.context import (
    correlation_scope,
    get_request_id,
    get_traceparent,
    safe_request_id,
)
from arangodb_mcp.observability.conventions import (
    ATTR_CONVENTION_VERSION,
    ATTR_OUTCOME,
    ATTR_REQUEST_ID,
    ATTR_TRANSPORT,
    CONVENTION_VERSION,
    SPAN_MCP_REQUEST,
)
from arangodb_mcp.observability.telemetry import get_tracer

__all__ = ["RequestContextMiddleware", "get_request_id"]


class RequestContextMiddleware:
    """Propagate a safe request ID through context and response headers."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request_id = safe_request_id(_header(scope, b"x-request-id"))
        traceparent = _header(scope, b"traceparent")
        parent_context = extract({"traceparent": traceparent}) if traceparent else None
        with (
            correlation_scope(request_id=request_id, traceparent=traceparent),
            get_tracer().start_as_current_span(
                SPAN_MCP_REQUEST,
                context=parent_context,
                attributes={
                    ATTR_CONVENTION_VERSION: CONVENTION_VERSION,
                    ATTR_REQUEST_ID: request_id,
                    ATTR_TRANSPORT: "http",
                    "http.request.method": scope.get("method", ""),
                    "url.path": scope.get("path", ""),
                },
            ) as span,
        ):

            async def send_with_context(message):
                if message["type"] == "http.response.start":
                    status = int(message.get("status", 200))
                    outcome = "success" if status < 400 else "error"
                    span.set_attribute("http.response.status_code", status)
                    span.set_attribute(ATTR_OUTCOME, outcome)
                    if status >= 500:
                        span.set_status(Status(StatusCode.ERROR))
                    headers = [
                        (name, value)
                        for name, value in message.get("headers", [])
                        if name.lower() not in {b"x-request-id", b"traceparent"}
                    ]
                    headers.append((b"x-request-id", request_id.encode("ascii")))
                    response_traceparent = get_traceparent()
                    if response_traceparent is not None:
                        headers.append((b"traceparent", response_traceparent.encode("ascii")))
                    message = {**message, "headers": headers}
                await send(message)

            await self.app(scope, receive, send_with_context)


def _header(scope, name: bytes) -> str | None:
    for header_name, value in scope.get("headers", []):
        if header_name.lower() == name:
            return value.decode("ascii", errors="ignore")
    return None
