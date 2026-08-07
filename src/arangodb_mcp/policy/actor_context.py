"""Request-scoped authenticated identity and database credentials."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


@dataclass(frozen=True)
class ArangoCredentials:
    """Server-resolved credentials; access tokens never populate these fields."""

    username: str
    password: str = field(repr=False)
    databases: frozenset[str]


@dataclass(frozen=True)
class RequestIdentity:
    """Validated OAuth identity and its effective database authority."""

    actor_id: str
    issuer: str
    subject: str
    oauth_scopes: frozenset[str]
    databases: frozenset[str]
    credentials: ArangoCredentials


_actor_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "mcp_actor_id", default="local-stdio"
)
_request_identity: contextvars.ContextVar[RequestIdentity | None] = contextvars.ContextVar(
    "mcp_request_identity", default=None
)


def get_actor_id() -> str:
    """Return the server-established actor for the current request."""
    identity = _request_identity.get()
    return identity.actor_id if identity is not None else _actor_id.get()


def get_request_identity() -> RequestIdentity | None:
    """Return the validated OAuth identity, if this is an OIDC request."""
    return _request_identity.get()


@contextmanager
def actor_scope(actor_id: str, identity: RequestIdentity | None = None) -> Iterator[None]:
    """Bind an actor for one authenticated request and restore it afterwards."""
    actor_token = _actor_id.set(actor_id)
    identity_token = _request_identity.set(identity)
    try:
        yield
    finally:
        _request_identity.reset(identity_token)
        _actor_id.reset(actor_token)


@contextmanager
def identity_scope(identity: RequestIdentity) -> Iterator[None]:
    """Bind one validated identity without leaking it to concurrent requests."""
    with actor_scope(identity.actor_id, identity):
        yield
