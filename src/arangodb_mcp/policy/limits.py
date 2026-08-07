"""Central hard ceilings for tool inputs, runtime, concurrency, and outputs."""

from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping

from pydantic import TypeAdapter

from arangodb_mcp.catalog.loader import ToolLimits
from arangodb_mcp.observability.metrics import (
    limiter_inflight,
    limiter_rejected,
    set_rate_limit_remaining,
)

_JSON_VALUE = TypeAdapter(Any)
_ROW_FIELDS = frozenset(
    {
        "analyzers",
        "backups",
        "collections",
        "databases",
        "documents",
        "edges",
        "indexes",
        "items",
        "neighbors",
        "paths",
        "results",
        "servers",
        "transactions",
        "users",
        "vertices",
        "views",
    }
)


@dataclass(frozen=True)
class HardCeilings:
    max_runtime_ms: int = 120_000
    max_rows: int = 1_000
    max_response_bytes: int = 2_097_152
    max_bulk_items: int = 1_000
    max_concurrency: int = 16


HARD_CEILINGS = HardCeilings()
MAX_AQL_RUNTIME_SECONDS = 30.0


@dataclass(frozen=True)
class LimitViolation:
    code: str
    message: str
    dimension: str
    maximum: int
    actual: int
    retry_after_ms: int | None = None

    def as_metadata(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


def effective_limits(configured: ToolLimits) -> ToolLimits:
    """Clamp catalog policy to non-disableable code-level production ceilings."""
    return ToolLimits(
        max_runtime_ms=min(configured.max_runtime_ms, HARD_CEILINGS.max_runtime_ms),
        max_rows=min(configured.max_rows, HARD_CEILINGS.max_rows),
        max_response_bytes=min(configured.max_response_bytes, HARD_CEILINGS.max_response_bytes),
        max_bulk_items=min(configured.max_bulk_items, HARD_CEILINGS.max_bulk_items),
        max_concurrency=min(configured.max_concurrency, HARD_CEILINGS.max_concurrency),
    )


def effective_aql_runtime(requested: float | None, configured_default: float) -> float:
    """Apply a non-disableable AQL runtime ceiling despite zero/oversized overrides."""
    candidate = configured_default if requested is None else requested
    if candidate <= 0:
        return MAX_AQL_RUNTIME_SECONDS
    return min(float(candidate), MAX_AQL_RUNTIME_SECONDS)


def check_bulk_input(arguments: Mapping[str, Any], maximum: int) -> LimitViolation | None:
    """Reject any nested input array that exceeds the tool's bulk ceiling."""
    largest = 0
    stack: list[Any] = [arguments]
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            stack.extend(value.values())
        elif isinstance(value, list | tuple):
            largest = max(largest, len(value))
            stack.extend(value)
    if largest <= maximum:
        return None
    return LimitViolation(
        code="bulk_input_limit_exceeded",
        message=f"Input array contains {largest} items; maximum is {maximum}",
        dimension="bulk_items",
        maximum=maximum,
        actual=largest,
    )


def truncate_rows(value: Any, maximum: int) -> tuple[Any, list[dict[str, Any]]]:
    """Truncate known row-bearing fields while preserving non-row arrays such as vectors."""
    truncated: list[dict[str, Any]] = []

    def visit(current: Any, path: str) -> Any:
        if isinstance(current, Mapping):
            output: dict[str, Any] = {}
            for key, child in current.items():
                child_path = f"{path}.{key}" if path else str(key)
                if key in _ROW_FIELDS and isinstance(child, list) and len(child) > maximum:
                    output[key] = child[:maximum]
                    truncated.append(
                        {
                            "path": child_path,
                            "actual": len(child),
                            "returned": maximum,
                            "maximum": maximum,
                        }
                    )
                else:
                    output[key] = visit(child, child_path)
            return output
        if isinstance(current, tuple):
            return tuple(visit(child, f"{path}[]") for child in current)
        return current

    return visit(value, ""), truncated


def serialized_size(value: Any) -> int:
    serializable = _JSON_VALUE.dump_python(value, mode="json")
    return len(json.dumps(serializable, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))


class ConcurrencyLimiter:
    """Atomically reject work above a per-tool concurrency ceiling."""

    def __init__(self) -> None:
        self._active: dict[str, int] = {}
        self._lock = threading.Lock()

    def acquire(self, tool_name: str, maximum: int) -> LimitViolation | None:
        with self._lock:
            active = self._active.get(tool_name, 0)
            if active >= maximum:
                return LimitViolation(
                    code="concurrency_limit_exceeded",
                    message=f"Tool {tool_name!r} has reached its concurrency limit",
                    dimension="concurrency",
                    maximum=maximum,
                    actual=active,
                    retry_after_ms=250,
                )
            self._active[tool_name] = active + 1
        return None

    def release(self, tool_name: str) -> None:
        with self._lock:
            active = self._active.get(tool_name, 0)
            if active <= 1:
                self._active.pop(tool_name, None)
            else:
                self._active[tool_name] = active - 1


@dataclass
class _ActorBucket:
    tokens: float
    updated_at: float
    last_seen: float


class OperationsLimiter:
    """Atomic actor-rate plus global/class/tool concurrency enforcement."""

    def __init__(
        self,
        *,
        actor_rate_per_minute: int,
        actor_burst: int,
        global_maximum: int,
        class_maxima: Mapping[str, int],
        retry_after_ms: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.actor_rate_per_minute = actor_rate_per_minute
        self.actor_burst = actor_burst
        self.global_maximum = global_maximum
        self.class_maxima = dict(class_maxima)
        self.retry_after_ms = retry_after_ms
        self._clock = clock
        self._actors: dict[str, _ActorBucket] = {}
        self._global_active = 0
        self._class_active: dict[str, int] = {}
        self._tool_active: dict[str, int] = {}
        self._lock = threading.Lock()

    def acquire(
        self,
        *,
        actor: str,
        tool_name: str,
        limit_class: str,
        tool_maximum: int,
    ) -> LimitViolation | None:
        now = self._clock()
        with self._lock:
            bucket = self._refill_actor(actor, now)
            if bucket.tokens < 1:
                wait_ms = max(
                    1,
                    math.ceil((1 - bucket.tokens) * 60_000 / self.actor_rate_per_minute),
                )
                limiter_rejected("actor", limit_class, "rate")
                set_rate_limit_remaining(min(item.tokens for item in self._actors.values()))
                return LimitViolation(
                    code="rate_limit_exceeded",
                    message="Actor request rate limit has been reached",
                    dimension="rate_per_minute",
                    maximum=self.actor_rate_per_minute,
                    actual=self.actor_rate_per_minute,
                    retry_after_ms=wait_ms,
                )
            bucket.tokens -= 1
            set_rate_limit_remaining(min(item.tokens for item in self._actors.values()))

            class_maximum = self.class_maxima.get(limit_class, self.global_maximum)
            checks = (
                ("global", self._global_active, self.global_maximum),
                (
                    "class",
                    self._class_active.get(limit_class, 0),
                    class_maximum,
                ),
                ("tool", self._tool_active.get(tool_name, 0), tool_maximum),
            )
            for scope, active, maximum in checks:
                if active >= maximum:
                    limiter_rejected(scope, limit_class, "concurrency")
                    code = (
                        "concurrency_limit_exceeded"
                        if scope == "tool"
                        else f"{scope}_concurrency_limit_exceeded"
                    )
                    return LimitViolation(
                        code=code,
                        message=f"{scope.title()} concurrency limit has been reached",
                        dimension=f"{scope}_concurrency",
                        maximum=maximum,
                        actual=active,
                        retry_after_ms=self.retry_after_ms,
                    )

            self._global_active += 1
            self._class_active[limit_class] = self._class_active.get(limit_class, 0) + 1
            self._tool_active[tool_name] = self._tool_active.get(tool_name, 0) + 1
            limiter_inflight("global", "all", 1)
            limiter_inflight("class", limit_class, 1)
            limiter_inflight("tool", limit_class, 1)
            self._expire_actor_buckets(now)
            return None

    def release(self, *, tool_name: str, limit_class: str) -> None:
        with self._lock:
            if self._tool_active.get(tool_name, 0) <= 0:
                return
            self._global_active -= 1
            self._decrement(self._class_active, limit_class)
            self._decrement(self._tool_active, tool_name)
            limiter_inflight("global", "all", -1)
            limiter_inflight("class", limit_class, -1)
            limiter_inflight("tool", limit_class, -1)

    def snapshot(self) -> dict[str, Any]:
        """Return state without actor identifiers for health/tests."""
        with self._lock:
            return {
                "global": self._global_active,
                "classes": dict(self._class_active),
                "tools": dict(self._tool_active),
                "actor_bucket_count": len(self._actors),
            }

    def _refill_actor(self, actor: str, now: float) -> _ActorBucket:
        bucket = self._actors.get(actor)
        if bucket is None:
            bucket = _ActorBucket(float(self.actor_burst), now, now)
            self._actors[actor] = bucket
        elapsed = max(0.0, now - bucket.updated_at)
        bucket.tokens = min(
            float(self.actor_burst),
            bucket.tokens + elapsed * self.actor_rate_per_minute / 60,
        )
        bucket.updated_at = now
        bucket.last_seen = now
        return bucket

    def _expire_actor_buckets(self, now: float) -> None:
        if len(self._actors) <= 10_000:
            return
        cutoff = now - 600
        stale = [actor for actor, bucket in self._actors.items() if bucket.last_seen < cutoff]
        for actor in stale:
            self._actors.pop(actor, None)
        overflow = len(self._actors) - 10_000
        if overflow > 0:
            oldest = sorted(self._actors, key=lambda actor: self._actors[actor].last_seen)[
                :overflow
            ]
            for actor in oldest:
                self._actors.pop(actor, None)

    @staticmethod
    def _decrement(active: dict[str, int], key: str) -> None:
        value = active.get(key, 0)
        if value <= 1:
            active.pop(key, None)
        else:
            active[key] = value - 1


def parse_class_concurrency_limits(value: str) -> dict[str, int]:
    """Parse and validate configured catalog limit-class ceilings."""
    parsed: dict[str, int] = {}
    for item in value.split(","):
        if not item.strip():
            continue
        name, separator, maximum = item.partition("=")
        if not separator or not name.strip():
            raise ValueError(f"Invalid class concurrency limit entry: {item!r}")
        try:
            number = int(maximum)
        except ValueError as exc:
            raise ValueError(f"Invalid class concurrency maximum: {item!r}") from exc
        if number <= 0:
            raise ValueError(f"Class concurrency maximum must be positive: {item!r}")
        parsed[name.strip()] = number
    if not parsed:
        raise ValueError("At least one MCP_CLASS_CONCURRENCY_LIMITS entry is required")
    return parsed
