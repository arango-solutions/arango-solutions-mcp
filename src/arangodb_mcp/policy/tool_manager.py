"""Catalog-enforcing, profile-filtered MCP tool manager."""

from __future__ import annotations

import json
import time
from contextlib import nullcontext
from typing import Any, Callable

import anyio
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.tools.base import Tool
from mcp.server.fastmcp.tools.tool_manager import ToolManager
from mcp.types import TextContent
from opentelemetry.trace import Status, StatusCode
from pydantic import TypeAdapter

from arangodb_mcp.catalog.loader import ToolCatalog
from arangodb_mcp.config import settings
from arangodb_mcp.contracts.v3_result import V3_RESULT_SCHEMA, normalize_result
from arangodb_mcp.observability.audit import emit_catalog_audit
from arangodb_mcp.observability.context import correlation_scope, get_request_id
from arangodb_mcp.observability.conventions import (
    ATTR_CONVENTION_VERSION,
    ATTR_OUTCOME,
    ATTR_REQUEST_ID,
    ATTR_TOOL_CATEGORY,
    ATTR_TOOL_NAME,
    ATTR_TOOL_OPERATION,
    ATTR_TRANSPORT,
    CONVENTION_VERSION,
    SPAN_MCP_REQUEST,
    SPAN_MCP_TOOL_CALL,
)
from arangodb_mcp.observability.metrics import observe_tool
from arangodb_mcp.observability.telemetry import get_tracer
from arangodb_mcp.policy.actor_context import RequestIdentity, get_actor_id, get_request_identity
from arangodb_mcp.policy.confirmation import (
    ConfirmationError,
    ConfirmationVerifier,
    conditional_confirmation_scope,
)
from arangodb_mcp.policy.limits import (
    LimitViolation,
    OperationsLimiter,
    check_bulk_input,
    effective_limits,
    parse_class_concurrency_limits,
    serialized_size,
    truncate_rows,
)
from arangodb_mcp.policy.profiles import ProfileSelection

_JSON_VALUE = TypeAdapter(Any)
_OPERATION_SCOPE = {
    "read": "mcp:read",
    "write": "mcp:write",
    "admin": "mcp:admin",
}


class PolicyToolManager(ToolManager):
    """Register only policy-visible tools while retaining completeness evidence."""

    def __init__(
        self,
        *,
        catalog: ToolCatalog,
        selection: ProfileSelection,
        result_contract: str,
        confirmation_secret: str | None = None,
        warn_on_duplicate_tools: bool = True,
    ) -> None:
        super().__init__(warn_on_duplicate_tools=warn_on_duplicate_tools)
        self.catalog = catalog
        self.selection = selection
        self.result_contract = result_contract
        self._confirmation_verifier = (
            ConfirmationVerifier(confirmation_secret) if confirmation_secret else None
        )
        ops = settings.observability
        self._operations = OperationsLimiter(
            actor_rate_per_minute=ops.mcp_actor_rate_limit_per_minute,
            actor_burst=ops.mcp_actor_rate_limit_burst,
            global_maximum=ops.mcp_global_max_concurrency,
            class_maxima=parse_class_concurrency_limits(ops.mcp_class_concurrency_limits),
            retry_after_ms=ops.mcp_limiter_retry_after_ms,
        )
        self._registered_tools: dict[str, Tool] = {}

    def add_tool(
        self,
        fn: Callable[..., Any],
        name: str | None = None,
        title: str | None = None,
        description: str | None = None,
        annotations: Any = None,
        icons: Any = None,
        meta: dict[str, Any] | None = None,
        structured_output: bool | None = None,
    ) -> Tool:
        resolved_name = name or fn.__name__
        definition = self.catalog.get(resolved_name)
        catalog_meta = {
            "category": definition.category,
            "risk": definition.risk,
            "operation": definition.operation,
            "scope": definition.scope,
            "confirmation": definition.confirmation,
        }
        merged_meta = dict(meta or {})
        merged_meta["policy"] = catalog_meta
        tool = super().add_tool(
            fn,
            name=name,
            title=title,
            description=description,
            annotations=annotations,
            icons=icons,
            meta=merged_meta,
            structured_output=structured_output,
        )
        self._registered_tools[tool.name] = tool
        if self.result_contract == "v3":
            tool.fn_metadata.output_schema = V3_RESULT_SCHEMA
            tool.__dict__.pop("output_schema", None)
        if definition.confirmation in {"human", "conditional"}:
            parameters = dict(tool.parameters)
            properties = dict(parameters.get("properties", {}))
            properties["confirmation_token"] = {
                "type": "string",
                "description": (
                    "Short-lived actor/action/parameter-bound token minted by the trusted "
                    "out-of-band operator CLI."
                ),
            }
            parameters["properties"] = properties
            if definition.confirmation == "human":
                parameters["required"] = [
                    *parameters.get("required", []),
                    "confirmation_token",
                ]
            tool.parameters = parameters
        if tool.name not in self.selection.active_tools:
            self._tools.pop(tool.name, None)
        return tool

    def finalize_registration(self) -> None:
        """Fail startup when code and catalog inventory diverge in either direction."""
        self.catalog.validate_registered(self._registered_tools)
        missing_active = self.selection.active_tools - self._tools.keys()
        if missing_active:
            raise RuntimeError(
                f"Active catalog tools were not registered: {sorted(missing_active)}"
            )

    def all_registered_tools(self) -> list[Tool]:
        """Return all catalog-validated tools for audit and contract tests."""
        return list(self._registered_tools.values())

    def list_tools(self) -> list[Tool]:
        """Expose only the startup-policy and current token-scope intersection."""
        tools = super().list_tools()
        identity = get_request_identity()
        if identity is None:
            return tools
        return [
            tool
            for tool in tools
            if _OPERATION_SCOPE[self.catalog.get(tool.name).operation] in identity.oauth_scopes
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        context: Any = None,
        convert_result: bool = False,
    ) -> Any:
        """Dispatch with one correlation root, tool span, metric, and audit boundary."""
        definition = self.catalog.get(name)
        had_request = get_request_id() is not None
        with correlation_scope():
            request_span = (
                nullcontext()
                if had_request
                else get_tracer().start_as_current_span(
                    SPAN_MCP_REQUEST,
                    attributes={
                        ATTR_CONVENTION_VERSION: CONVENTION_VERSION,
                        ATTR_REQUEST_ID: get_request_id() or "",
                        ATTR_TRANSPORT: "stdio",
                    },
                )
            )
            with request_span:
                started = time.perf_counter()
                outcome = "error"
                with get_tracer().start_as_current_span(
                    SPAN_MCP_TOOL_CALL,
                    attributes={
                        ATTR_CONVENTION_VERSION: CONVENTION_VERSION,
                        ATTR_REQUEST_ID: get_request_id() or "",
                        ATTR_TOOL_NAME: name,
                        ATTR_TOOL_OPERATION: definition.operation,
                        ATTR_TOOL_CATEGORY: definition.category,
                    },
                ) as span:
                    try:
                        result = await self._call_tool_inner(
                            name,
                            arguments,
                            context=context,
                            convert_result=convert_result,
                        )
                        outcome = _result_outcome(result)
                        span.set_attribute(ATTR_OUTCOME, outcome)
                        if outcome == "error":
                            span.set_status(Status(StatusCode.ERROR))
                        return result
                    except ToolError as exc:
                        outcome = "denied" if "unavailable" in str(exc) else "error"
                        span.set_attribute(ATTR_OUTCOME, outcome)
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
                        raise
                    except Exception as exc:
                        span.record_exception(exc)
                        span.set_attribute(ATTR_OUTCOME, "error")
                        span.set_status(Status(StatusCode.ERROR))
                        raise
                    finally:
                        observe_tool(
                            name,
                            definition.operation,
                            "error" if outcome == "error" else outcome,
                            time.perf_counter() - started,
                        )
                        if definition.operation in {"write", "admin"}:
                            emit_catalog_audit(
                                definition=definition,
                                action=name,
                                arguments=arguments,
                                outcome=outcome,
                            )

    async def _call_tool_inner(
        self,
        name: str,
        arguments: dict[str, Any],
        context: Any = None,
        convert_result: bool = False,
    ) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"Tool {name!r} is unavailable under the active MCP policy")

        definition = self.catalog.get(name)
        identity = get_request_identity()
        authorization_error = _authorize_request(identity, definition, arguments)
        if authorization_error is not None:
            normalized = normalize_result(name, authorization_error, contract=self.result_contract)
            if convert_result:
                if self.result_contract == "v3":
                    structured = _JSON_VALUE.dump_python(normalized, mode="json")
                    content = [TextContent(type="text", text=json.dumps(structured, indent=2))]
                    return content, structured
                return tool.fn_metadata.convert_result(normalized)
            return normalized

        limits = effective_limits(definition.limits)
        call_arguments = dict(arguments)
        policy_metadata: dict[str, Any] = {}
        conditional_token = (
            call_arguments.pop("confirmation_token", None)
            if definition.confirmation == "conditional"
            else None
        )

        limiter_violation = self._operations.acquire(
            actor=get_actor_id(),
            tool_name=name,
            limit_class=definition.limit_class,
            tool_maximum=limits.max_concurrency,
        )
        if limiter_violation is not None:
            result = _violation_result(limiter_violation)
            policy_metadata["limit"] = limiter_violation.as_metadata()
        else:
            try:
                violation = check_bulk_input(call_arguments, limits.max_bulk_items)
                if violation is not None:
                    result = _violation_result(violation)
                    policy_metadata["limit"] = violation.as_metadata()
                else:
                    confirmation_error = self._verify_confirmation(
                        name, definition.confirmation, call_arguments
                    )
                    if confirmation_error is not None:
                        result = {
                            "error": str(confirmation_error),
                            "error_code": confirmation_error.code,
                        }
                        policy_metadata["confirmation"] = {
                            "required": True,
                            "verified": False,
                            "code": confirmation_error.code,
                        }
                    else:
                        confirmation_scope = (
                            conditional_confirmation_scope(
                                verifier=self._confirmation_verifier,
                                token=conditional_token,
                                actor=get_actor_id(),
                                action=name,
                                arguments=call_arguments,
                            )
                            if definition.confirmation == "conditional"
                            else nullcontext()
                        )
                        try:
                            with confirmation_scope:
                                with anyio.fail_after(limits.max_runtime_ms / 1000):
                                    result = await tool.run(
                                        call_arguments,
                                        context=context,
                                        convert_result=False,
                                    )
                        except TimeoutError:
                            timeout = LimitViolation(
                                code="runtime_limit_exceeded",
                                message=f"Tool {name!r} exceeded its runtime ceiling",
                                dimension="runtime_ms",
                                maximum=limits.max_runtime_ms,
                                actual=limits.max_runtime_ms,
                            )
                            result = _violation_result(timeout)
                            policy_metadata["limit"] = timeout.as_metadata()
                        except ToolError as exc:
                            result = {
                                "error": str(exc),
                                "error_code": "tool_execution_error",
                            }
            finally:
                self._operations.release(tool_name=name, limit_class=definition.limit_class)

        result, truncated = truncate_rows(result, limits.max_rows)
        if truncated:
            policy_metadata["truncation"] = {
                "code": "row_limit_truncated",
                "dimension": "rows",
                "fields": truncated,
            }
        actual_bytes = serialized_size(result)
        if actual_bytes > limits.max_response_bytes - 2048:
            response_violation = LimitViolation(
                code="response_size_limit_exceeded",
                message=f"Tool {name!r} response exceeded its byte ceiling",
                dimension="response_bytes",
                maximum=limits.max_response_bytes,
                actual=actual_bytes,
            )
            result = _violation_result(response_violation)
            policy_metadata["limit"] = response_violation.as_metadata()

        normalized = normalize_result(name, result, contract=self.result_contract)
        if policy_metadata and isinstance(normalized, dict) and "meta" in normalized:
            normalized["meta"]["policy"] = policy_metadata
        if convert_result:
            if self.result_contract == "v3":
                structured = _JSON_VALUE.dump_python(normalized, mode="json")
                content = [TextContent(type="text", text=json.dumps(structured, indent=2))]
                return content, structured
            return tool.fn_metadata.convert_result(normalized)
        return normalized

    def _verify_confirmation(
        self,
        tool_name: str,
        confirmation_policy: str,
        arguments: dict[str, Any],
    ) -> ConfirmationError | None:
        if confirmation_policy != "human":
            return None
        token = arguments.pop("confirmation_token", None)
        if self._confirmation_verifier is None:
            return ConfirmationError(
                "confirmation_not_configured",
                "Human confirmation is required but MCP_CONFIRMATION_SECRET is not configured",
            )
        try:
            self._confirmation_verifier.verify_and_consume(
                token,
                actor=get_actor_id(),
                action=tool_name,
                arguments=arguments,
            )
        except ConfirmationError as exc:
            return exc
        return None


def _violation_result(violation: LimitViolation) -> dict[str, Any]:
    return {
        "error": violation.message,
        "error_code": violation.code,
        "limit": violation.as_metadata(),
    }


def _result_outcome(result: Any) -> str:
    """Map every result shape to the fixed success/denied/error vocabulary."""
    candidate = result[1] if isinstance(result, tuple) and len(result) == 2 else result
    if not isinstance(candidate, dict):
        return "success"
    if candidate.get("status") == "success":
        return "success"
    error = candidate.get("error")
    if isinstance(error, dict):
        code = str(error.get("code", ""))
    else:
        code = str(candidate.get("error_code", ""))
        if not error:
            return "success"
    denied_markers = (
        "denied",
        "limit_exceeded",
        "insufficient_scope",
        "confirmation_",
        "aql_policy_",
    )
    return "denied" if any(marker in code for marker in denied_markers) else "error"


def _authorize_request(
    identity: RequestIdentity | None,
    definition: Any,
    arguments: dict[str, Any],
) -> dict[str, Any] | None:
    if identity is None:
        return None
    required_scope = _OPERATION_SCOPE[definition.operation]
    if required_scope not in identity.oauth_scopes:
        return {
            "error": f"OAuth scope {required_scope!r} is required for this operation",
            "error_code": "insufficient_scope",
            "required_scope": required_scope,
        }
    database = _database_target(definition, arguments)
    if database is not None and database not in identity.databases:
        return {
            "error": f"Database {database!r} is outside the request authority",
            "error_code": "database_access_denied",
            "database": database,
        }
    return None


def _database_target(definition: Any, arguments: dict[str, Any]) -> str | None:
    """Resolve execution database without confusing OAuth and catalog scopes."""
    if definition.category == "manual" or definition.scope == "external":
        return None
    if definition.category == "identity" or definition.name in {
        "list-databases",
        "create-database",
        "delete-database",
    }:
        return "_system"
    requested = arguments.get("database_name")
    if isinstance(requested, str) and requested:
        return requested
    return settings.arango.default_db_name
