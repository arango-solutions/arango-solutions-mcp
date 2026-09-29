"""Server-side actor-to-ArangoDB credential mapping."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from arangodb_mcp.policy.actor_context import ArangoCredentials


class CredentialConfigurationError(ValueError):
    """Raised when the trusted credential mapping is malformed."""


class CredentialResolutionError(PermissionError):
    """Raised when no least-privilege credential is configured for an actor."""


class StaticCredentialProvider:
    """Resolve credentials from a trusted server-side JSON mapping.

    Entries are keyed by the validated token subject (or ``"*"`` as an explicit
    fallback). Passwords may be literal server configuration or, preferably,
    references to separate environment variables via ``password_env``.
    """

    def __init__(self, mapping: Mapping[str, ArangoCredentials]) -> None:
        if not mapping:
            raise CredentialConfigurationError("OIDC credential mapping must not be empty")
        self._mapping = dict(mapping)

    @classmethod
    def from_json(cls, raw: str) -> StaticCredentialProvider:
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CredentialConfigurationError(
                "MCP_ARANGO_CREDENTIALS_JSON must be valid JSON"
            ) from exc
        if not isinstance(document, dict):
            raise CredentialConfigurationError(
                "MCP_ARANGO_CREDENTIALS_JSON must be an actor-keyed object"
            )
        return cls(
            {
                actor: _parse_entry(actor, entry)
                for actor, entry in document.items()
                if _validate_actor_key(actor)
            }
        )

    def resolve(self, actor_id: str) -> ArangoCredentials:
        credentials = self._mapping.get(actor_id) or self._mapping.get("*")
        if credentials is None:
            raise CredentialResolutionError(
                "No server-side ArangoDB credential is configured for this actor"
            )
        return credentials


def _validate_actor_key(actor: Any) -> bool:
    if not isinstance(actor, str) or not actor:
        raise CredentialConfigurationError(
            "Credential mapping actor keys must be non-empty strings"
        )
    return True


def _parse_entry(actor: str, raw: Any) -> ArangoCredentials:
    if not isinstance(raw, dict):
        raise CredentialConfigurationError(f"Credential mapping for {actor!r} must be an object")
    allowed = {"username", "password", "password_env", "databases"}
    unknown = set(raw) - allowed
    if unknown:
        raise CredentialConfigurationError(
            f"Credential mapping for {actor!r} has unknown fields: {sorted(unknown)}"
        )

    username = raw.get("username")
    databases = raw.get("databases")
    if not isinstance(username, str) or not username:
        raise CredentialConfigurationError(
            f"Credential mapping for {actor!r} requires a non-empty username"
        )
    if (
        not isinstance(databases, list)
        or not databases
        or not all(isinstance(item, str) and item for item in databases)
    ):
        raise CredentialConfigurationError(
            f"Credential mapping for {actor!r} requires non-empty string databases"
        )

    password = raw.get("password")
    password_env = raw.get("password_env")
    if bool(password) == bool(password_env):
        raise CredentialConfigurationError(
            f"Credential mapping for {actor!r} must set exactly one of password or password_env"
        )
    if password_env:
        if not isinstance(password_env, str):
            raise CredentialConfigurationError(
                f"password_env for {actor!r} must be a non-empty string"
            )
        password = os.environ.get(password_env)
        if not password:
            raise CredentialConfigurationError(
                f"Credential password environment variable {password_env!r} is unset"
            )
    if not isinstance(password, str) or not password:
        raise CredentialConfigurationError(
            f"Credential mapping for {actor!r} requires a non-empty password"
        )

    return ArangoCredentials(
        username=username,
        password=password,
        databases=frozenset(databases),
    )
