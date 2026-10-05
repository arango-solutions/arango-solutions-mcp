"""Signed, actor-bound, one-use human confirmation tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator, Mapping

TOKEN_VERSION = 1
MAX_CONFIRMATION_TTL_SECONDS = 300


class ConfirmationError(ValueError):
    """Raised when a confirmation token is missing, invalid, expired, or replayed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ConfirmationClaims:
    actor: str
    action: str
    parameters_sha256: str
    issued_at: int
    expires_at: int
    token_id: str


@dataclass(frozen=True)
class PendingConfirmation:
    verifier: ConfirmationVerifier | None
    token: str | None
    actor: str
    action: str
    arguments: Mapping[str, Any]


_pending_confirmation: ContextVar[PendingConfirmation | None] = ContextVar(
    "mcp_pending_confirmation", default=None
)


def canonical_parameters_hash(arguments: Mapping[str, Any]) -> str:
    """Hash canonical JSON arguments so approval cannot be reused with changed parameters."""
    encoded = json.dumps(
        arguments,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, TypeError) as exc:
        raise ConfirmationError("confirmation_invalid", "Malformed confirmation token") from exc


def mint_confirmation_token(
    *,
    secret: str,
    actor: str,
    action: str,
    arguments: Mapping[str, Any],
    ttl_seconds: int = 120,
    now: int | None = None,
) -> str:
    """Mint a token from a trusted host-side workflow, never from an MCP tool."""
    if not secret:
        raise ValueError("Confirmation secret must be non-empty")
    if not actor or not action:
        raise ValueError("Actor and action must be non-empty")
    if not 1 <= ttl_seconds <= MAX_CONFIRMATION_TTL_SECONDS:
        raise ValueError(f"ttl_seconds must be between 1 and {MAX_CONFIRMATION_TTL_SECONDS}")
    issued_at = int(time.time()) if now is None else now
    payload = {
        "v": TOKEN_VERSION,
        "jti": secrets.token_urlsafe(18),
        "actor": actor,
        "action": action,
        "parameters_sha256": canonical_parameters_hash(arguments),
        "iat": issued_at,
        "exp": issued_at + ttl_seconds,
    }
    encoded = _b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature = _b64encode(
        hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{encoded}.{signature}"


class ConfirmationVerifier:
    """Verify and atomically consume signed confirmations once per server process."""

    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")
        self._consumed: set[str] = set()
        self._lock = threading.Lock()

    def verify_and_consume(
        self,
        token: str | None,
        *,
        actor: str,
        action: str,
        arguments: Mapping[str, Any],
        now: int | None = None,
    ) -> ConfirmationClaims:
        if not token:
            raise ConfirmationError(
                "confirmation_required",
                f"Tool {action!r} requires an out-of-band human confirmation token",
            )
        try:
            encoded, supplied_signature = token.split(".", 1)
        except ValueError as exc:
            raise ConfirmationError("confirmation_invalid", "Malformed confirmation token") from exc
        expected_signature = _b64encode(
            hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ConfirmationError("confirmation_invalid", "Invalid confirmation token signature")
        try:
            payload = json.loads(_b64decode(encoded))
            claims = ConfirmationClaims(
                actor=str(payload["actor"]),
                action=str(payload["action"]),
                parameters_sha256=str(payload["parameters_sha256"]),
                issued_at=int(payload["iat"]),
                expires_at=int(payload["exp"]),
                token_id=str(payload["jti"]),
            )
            version = int(payload["v"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ConfirmationError(
                "confirmation_invalid", "Malformed confirmation token claims"
            ) from exc

        current_time = int(time.time()) if now is None else now
        if version != TOKEN_VERSION:
            raise ConfirmationError(
                "confirmation_invalid", "Unsupported confirmation token version"
            )
        if claims.issued_at > current_time + 30:
            raise ConfirmationError(
                "confirmation_invalid", "Confirmation token issue time is in the future"
            )
        if claims.expires_at <= current_time:
            raise ConfirmationError("confirmation_expired", "Confirmation token has expired")
        if (
            claims.expires_at <= claims.issued_at
            or claims.expires_at - claims.issued_at > MAX_CONFIRMATION_TTL_SECONDS
        ):
            raise ConfirmationError(
                "confirmation_invalid", "Confirmation token lifetime exceeds policy"
            )
        if not hmac.compare_digest(claims.actor, actor):
            raise ConfirmationError(
                "confirmation_actor_mismatch",
                "Confirmation token is bound to a different actor",
            )
        if not hmac.compare_digest(claims.action, action):
            raise ConfirmationError(
                "confirmation_action_mismatch",
                "Confirmation token is bound to a different action",
            )
        expected_parameters = canonical_parameters_hash(arguments)
        if not hmac.compare_digest(claims.parameters_sha256, expected_parameters):
            raise ConfirmationError(
                "confirmation_parameters_mismatch",
                "Confirmation token is bound to different parameters",
            )

        with self._lock:
            if claims.token_id in self._consumed:
                raise ConfirmationError(
                    "confirmation_replayed", "Confirmation token has already been used"
                )
            self._consumed.add(claims.token_id)
        return claims


@contextmanager
def conditional_confirmation_scope(
    *,
    verifier: ConfirmationVerifier | None,
    token: str | None,
    actor: str,
    action: str,
    arguments: Mapping[str, Any],
) -> Iterator[None]:
    """Make an optional token available only to policy code reached during this call."""
    pending = PendingConfirmation(verifier, token, actor, action, dict(arguments))
    context_token = _pending_confirmation.set(pending)
    try:
        yield
    finally:
        _pending_confirmation.reset(context_token)


def consume_conditional_confirmation() -> ConfirmationClaims:
    """Verify a conditional token only after parser/policy code proves it is required."""
    pending = _pending_confirmation.get()
    if pending is None:
        raise ConfirmationError(
            "confirmation_required", "No conditional confirmation context is active"
        )
    if pending.verifier is None:
        raise ConfirmationError(
            "confirmation_not_configured",
            "Human confirmation is required but MCP_CONFIRMATION_SECRET is not configured",
        )
    return pending.verifier.verify_and_consume(
        pending.token,
        actor=pending.actor,
        action=pending.action,
        arguments=pending.arguments,
    )
