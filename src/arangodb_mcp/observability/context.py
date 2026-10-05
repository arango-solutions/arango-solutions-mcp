"""Transport-neutral request and W3C trace correlation context."""

from __future__ import annotations

import contextvars
import re
import secrets
import uuid
from contextlib import contextmanager
from typing import Iterator

from opentelemetry import trace

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_TRACEPARENT_PATTERN = re.compile(
    r"^(?P<version>[0-9a-f]{2})-(?P<trace_id>[0-9a-f]{32})-"
    r"(?P<span_id>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})$"
)
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "mcp_request_id", default=None
)
_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("mcp_trace_id", default=None)
_span_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("mcp_span_id", default=None)
_trace_flags: contextvars.ContextVar[str] = contextvars.ContextVar("mcp_trace_flags", default="01")


def safe_request_id(candidate: str | None) -> str:
    """Accept a bounded safe caller ID or create a server-owned one."""
    if candidate is not None and _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex


def parse_traceparent(value: str | None) -> tuple[str, str] | None:
    """Return a valid trace ID and flags from a W3C traceparent header."""
    if value is None:
        return None
    match = _TRACEPARENT_PATTERN.fullmatch(value.strip().lower())
    if match is None or match["version"] == "ff":
        return None
    trace_id = match["trace_id"]
    span_id = match["span_id"]
    if trace_id == "0" * 32 or span_id == "0" * 16:
        return None
    return trace_id, match["flags"]


def get_request_id() -> str | None:
    """Return the current request correlation ID."""
    return _request_id.get()


def get_trace_id() -> str | None:
    """Return the active OpenTelemetry or transport-neutral trace ID."""
    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        return trace.format_trace_id(span_context.trace_id)
    return _trace_id.get()


def get_traceparent() -> str | None:
    """Build the response/downstream W3C traceparent for the active request."""
    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        return (
            f"00-{trace.format_trace_id(span_context.trace_id)}-"
            f"{trace.format_span_id(span_context.span_id)}-{int(span_context.trace_flags):02x}"
        )
    trace_id = _trace_id.get()
    span_id = _span_id.get()
    if trace_id is None or span_id is None:
        return None
    return f"00-{trace_id}-{span_id}-{_trace_flags.get()}"


@contextmanager
def correlation_scope(
    *,
    request_id: str | None = None,
    traceparent: str | None = None,
) -> Iterator[None]:
    """Bind correlation IDs while preserving an existing parent request."""
    existing_request = get_request_id()
    resolved_request = existing_request or safe_request_id(request_id)
    parsed = parse_traceparent(traceparent)
    existing_trace = get_trace_id()
    resolved_trace = existing_trace or (parsed[0] if parsed else secrets.token_hex(16))
    flags = parsed[1] if parsed else "01"

    request_token = _request_id.set(resolved_request)
    trace_token = _trace_id.set(resolved_trace)
    span_token = _span_id.set(secrets.token_hex(8))
    flags_token = _trace_flags.set(flags)
    try:
        yield
    finally:
        _trace_flags.reset(flags_token)
        _span_id.reset(span_token)
        _trace_id.reset(trace_token)
        _request_id.reset(request_token)
