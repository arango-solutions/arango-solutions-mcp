"""Safety contracts for AQL classification, hard limits, and confirmations."""

from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from types import MappingProxyType
from unittest.mock import MagicMock, patch

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

os.environ.setdefault("ARANGO_HOSTS", "http://localhost:8529")
os.environ.setdefault("ARANGO_ROOT_USERNAME", "root")
os.environ.setdefault("ARANGO_ROOT_PASSWORD", "test")

from arangodb_mcp.agents.agent_base import ArangoAgentBase
from arangodb_mcp.agents.aql_execution_agent import AQLExecutionAgent
from arangodb_mcp.catalog.loader import ToolCatalog, load_tool_catalog
from arangodb_mcp.observability.context import get_request_id, get_trace_id
from arangodb_mcp.observability.telemetry import set_tracer_provider_for_testing
from arangodb_mcp.policy.actor_context import actor_scope
from arangodb_mcp.policy.aql_classifier import AQLClassification, classify_aql_parse_result
from arangodb_mcp.policy.confirmation import (
    ConfirmationError,
    ConfirmationVerifier,
    canonical_parameters_hash,
    mint_confirmation_token,
)
from arangodb_mcp.policy.context import PolicyContext
from arangodb_mcp.policy.limits import OperationsLimiter, effective_aql_runtime
from arangodb_mcp.policy.profiles import resolve_tool_inventory
from arangodb_mcp.policy.tool_manager import PolicyToolManager


def _parse_result(*nodes):
    return {"parsed": True, "ast": [{"type": "root", "subNodes": list(nodes)}]}


def _context(profile: str) -> PolicyContext:
    return PolicyContext(
        profile=profile,
        toolsets=frozenset(),
        denied_tools=frozenset(),
        denied_categories=frozenset(),
        result_contract="v3",
    )


def _catalog_with_limits(tool_name: str, **changes) -> ToolCatalog:
    catalog = load_tool_catalog()
    tools = dict(catalog.tools)
    definition = tools[tool_name]
    tools[tool_name] = replace(definition, limits=replace(definition.limits, **changes))
    return ToolCatalog(catalog.version, MappingProxyType(tools))


def _manager(
    catalog: ToolCatalog,
    *,
    profile: str = "admin",
    confirmation_secret: str | None = None,
) -> PolicyToolManager:
    return PolicyToolManager(
        catalog=catalog,
        selection=resolve_tool_inventory(catalog, _context(profile)),
        result_contract="v3",
        confirmation_secret=confirmation_secret,
    )


def test_parser_ast_classifies_read_mutation_and_ambiguous_queries():
    read = classify_aql_parse_result(
        _parse_result(
            {"type": "for", "subNodes": []},
            {"type": "return", "subNodes": []},
        )
    )
    mutation = classify_aql_parse_result(
        _parse_result(
            {
                "type": "subquery",
                "subNodes": [{"type": "upsert", "subNodes": []}],
            }
        )
    )
    ambiguous = classify_aql_parse_result(
        _parse_result({"type": "function call", "name": "CALL", "subNodes": []})
    )
    user_function = classify_aql_parse_result(
        _parse_result({"type": "user function call", "name": "ORG::LOOKUP"})
    )
    malformed = classify_aql_parse_result({"parsed": False})

    assert read.classification is AQLClassification.READ
    assert mutation.classification is AQLClassification.MUTATION
    assert mutation.mutation_nodes == ("upsert",)
    assert ambiguous.classification is AQLClassification.AMBIGUOUS
    assert user_function.classification is AQLClassification.AMBIGUOUS
    assert malformed.classification is AQLClassification.AMBIGUOUS


@pytest.mark.asyncio
async def test_readonly_agent_fails_closed_on_parser_identified_mutation(monkeypatch):
    db = MagicMock()
    db.name = "test"
    db.aql.validate.return_value = _parse_result({"type": "remove", "subNodes": []})
    connector = MagicMock()
    connector.get_db.return_value = db
    monkeypatch.setattr("arangodb_mcp.agents.agent_base.arango_connector", connector)

    async def run_sync(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(AQLExecutionAgent, "run_sync", staticmethod(run_sync))
    with patch("arangodb_mcp.agents.aql_execution_agent.settings.server.mcp_profile", "readonly"):
        result = await AQLExecutionAgent().arun(
            {"operation": "execute", "aql_query": "REMOVE d IN docs"}
        )

    assert result["error_code"] == "aql_policy_denied"
    assert result["classification"] == "mutation"
    db.aql.execute.assert_not_called()


@pytest.mark.asyncio
async def test_mutating_aql_requires_conditional_human_confirmation(monkeypatch):
    db = MagicMock()
    db.name = "test"
    db.aql.validate.return_value = _parse_result({"type": "insert", "subNodes": []})
    cursor = MagicMock()
    cursor.__iter__.return_value = iter([])
    cursor.count.return_value = 0
    cursor.full_count.return_value = 0
    cursor.statistics.return_value = {}
    db.aql.execute.return_value = cursor
    connector = MagicMock()
    connector.get_db.return_value = db
    monkeypatch.setattr("arangodb_mcp.agents.agent_base.arango_connector", connector)

    async def run_sync(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(AQLExecutionAgent, "run_sync", staticmethod(run_sync))
    secret = "operator-only-secret"
    manager = _manager(load_tool_catalog(), profile="developer", confirmation_secret=secret)
    agent = AQLExecutionAgent()

    async def execute_aql_query(aql_query):
        return await agent.arun({"operation": "execute", "aql_query": aql_query})

    manager.add_tool(execute_aql_query, name="execute-aql-query")
    arguments = {"aql_query": "INSERT {x: 1} INTO docs"}
    with patch("arangodb_mcp.agents.aql_execution_agent.settings.server.mcp_profile", "developer"):
        denied = await manager.call_tool("execute-aql-query", arguments)
        token = mint_confirmation_token(
            secret=secret,
            actor="alice",
            action="execute-aql-query",
            arguments=arguments,
        )
        with actor_scope("alice"):
            approved = await manager.call_tool(
                "execute-aql-query", {**arguments, "confirmation_token": token}
            )
    assert denied["error"]["code"] == "confirmation_required"
    assert approved["status"] == "success"
    assert approved["data"]["classification"] == "mutation"
    db.aql.execute.assert_called_once()


@pytest.mark.parametrize(
    "requested,configured,expected",
    [(None, 12.0, 12.0), (120.0, 12.0, 30.0), (0.0, 12.0, 30.0), (-1.0, 0.0, 30.0)],
)
def test_aql_runtime_ceiling_cannot_be_disabled(requested, configured, expected):
    assert effective_aql_runtime(requested, configured) == expected


@pytest.mark.asyncio
async def test_bulk_and_response_limits_deny_without_executing():
    catalog = load_tool_catalog()
    manager = _manager(catalog, profile="readonly")
    executed = False

    async def read_documents_with_filter(filters):
        nonlocal executed
        executed = True
        return {"results": []}

    manager.add_tool(read_documents_with_filter, name="read-documents-with-filter")
    result = await manager.call_tool(
        "read-documents-with-filter", {"filters": {"ids": list(range(1001))}}
    )
    assert result["error"]["code"] == "bulk_input_limit_exceeded"
    assert result["meta"]["policy"]["limit"]["dimension"] == "bulk_items"
    assert executed is False

    byte_manager = _manager(catalog, profile="readonly")

    async def list_databases():
        return {"blob": "x" * 1_100_000}

    byte_manager.add_tool(list_databases, name="list-databases")
    oversized = await byte_manager.call_tool("list-databases", {})
    assert oversized["error"]["code"] == "response_size_limit_exceeded"
    assert oversized["meta"]["policy"]["limit"]["dimension"] == "response_bytes"


@pytest.mark.asyncio
async def test_row_limit_truncates_with_machine_readable_metadata():
    manager = _manager(load_tool_catalog(), profile="readonly")

    async def list_databases():
        return {"databases": [f"db-{index}" for index in range(1500)]}

    manager.add_tool(list_databases, name="list-databases")
    result = await manager.call_tool("list-databases", {})
    assert result["status"] == "success"
    assert len(result["data"]["databases"]) == 1000
    truncation = result["meta"]["policy"]["truncation"]
    assert truncation["code"] == "row_limit_truncated"
    assert truncation["fields"][0]["actual"] == 1500


@pytest.mark.asyncio
async def test_runtime_and_concurrency_ceilings_deny_work():
    catalog = _catalog_with_limits("list-databases", max_runtime_ms=1000, max_concurrency=1)
    manager = _manager(catalog, profile="readonly")
    started = asyncio.Event()
    release = asyncio.Event()

    async def list_databases():
        started.set()
        await release.wait()
        return {"databases": []}

    manager.add_tool(list_databases, name="list-databases")
    first = asyncio.create_task(manager.call_tool("list-databases", {}))
    await started.wait()
    second = await manager.call_tool("list-databases", {})
    assert second["error"]["code"] == "concurrency_limit_exceeded"
    assert second["meta"]["policy"]["limit"]["retry_after_ms"] == 250
    release.set()
    assert (await first)["status"] == "success"

    timeout_catalog = _catalog_with_limits("list-databases", max_runtime_ms=1)
    timeout_manager = _manager(timeout_catalog, profile="readonly")

    async def slow_list_databases():
        await asyncio.sleep(0.05)
        return {"databases": []}

    timeout_manager.add_tool(slow_list_databases, name="list-databases")
    timed_out = await timeout_manager.call_tool("list-databases", {})
    assert timed_out["error"]["code"] == "runtime_limit_exceeded"


def test_actor_rate_limiter_returns_deterministic_retry_metadata():
    now = [100.0]
    limiter = OperationsLimiter(
        actor_rate_per_minute=60,
        actor_burst=1,
        global_maximum=2,
        class_maxima={"standard": 2},
        retry_after_ms=250,
        clock=lambda: now[0],
    )
    assert (
        limiter.acquire(
            actor="alice",
            tool_name="list-databases",
            limit_class="standard",
            tool_maximum=2,
        )
        is None
    )
    limiter.release(tool_name="list-databases", limit_class="standard")
    rejected = limiter.acquire(
        actor="alice",
        tool_name="list-databases",
        limit_class="standard",
        tool_maximum=2,
    )
    assert rejected is not None
    assert rejected.code == "rate_limit_exceeded"
    assert rejected.retry_after_ms == 1000
    now[0] += 1
    assert (
        limiter.acquire(
            actor="alice",
            tool_name="list-databases",
            limit_class="standard",
            tool_maximum=2,
        )
        is None
    )


@pytest.mark.asyncio
async def test_actor_rate_rejection_is_returned_in_v3_metadata():
    manager = _manager(load_tool_catalog(), profile="readonly")
    manager._operations = OperationsLimiter(
        actor_rate_per_minute=60,
        actor_burst=1,
        global_maximum=2,
        class_maxima={"standard": 2},
        retry_after_ms=250,
        clock=lambda: 100.0,
    )

    async def list_databases():
        return {"databases": []}

    manager.add_tool(list_databases, name="list-databases")
    assert (await manager.call_tool("list-databases", {}))["status"] == "success"
    rejected = await manager.call_tool("list-databases", {})
    assert rejected["error"]["code"] == "rate_limit_exceeded"
    assert rejected["meta"]["policy"]["limit"]["retry_after_ms"] == 1000


@pytest.mark.asyncio
async def test_global_concurrency_ceiling_is_never_exceeded():
    manager = _manager(load_tool_catalog(), profile="readonly")
    manager._operations = OperationsLimiter(
        actor_rate_per_minute=600,
        actor_burst=20,
        global_maximum=1,
        class_maxima={"standard": 2},
        retry_after_ms=321,
    )
    started = asyncio.Event()
    release = asyncio.Event()

    async def list_databases():
        started.set()
        await release.wait()
        return {"databases": []}

    async def list_collections():
        return {"collections": []}

    manager.add_tool(list_databases, name="list-databases")
    manager.add_tool(list_collections, name="list-collections")
    first = asyncio.create_task(manager.call_tool("list-databases", {}))
    await started.wait()
    assert manager._operations.snapshot()["global"] == 1
    rejected = await manager.call_tool("list-collections", {})
    assert rejected["error"]["code"] == "global_concurrency_limit_exceeded"
    assert rejected["meta"]["policy"]["limit"]["retry_after_ms"] == 321
    assert manager._operations.snapshot()["global"] == 1
    release.set()
    assert (await first)["status"] == "success"
    assert manager._operations.snapshot()["global"] == 0


@pytest.mark.asyncio
async def test_catalog_limit_class_concurrency_ceiling_is_never_exceeded():
    manager = _manager(load_tool_catalog(), profile="readonly")
    manager._operations = OperationsLimiter(
        actor_rate_per_minute=600,
        actor_burst=20,
        global_maximum=4,
        class_maxima={"standard": 1},
        retry_after_ms=250,
    )
    started = asyncio.Event()
    release = asyncio.Event()

    async def list_databases():
        started.set()
        await release.wait()
        return {"databases": []}

    async def list_collections():
        return {"collections": []}

    manager.add_tool(list_databases, name="list-databases")
    manager.add_tool(list_collections, name="list-collections")
    first = asyncio.create_task(manager.call_tool("list-databases", {}))
    await started.wait()
    rejected = await manager.call_tool("list-collections", {})
    assert rejected["error"]["code"] == "class_concurrency_limit_exceeded"
    assert manager._operations.snapshot()["classes"] == {"standard": 1}
    release.set()
    await first
    assert manager._operations.snapshot()["classes"] == {}


@pytest.mark.asyncio
async def test_trace_hierarchy_and_worker_context_propagation():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    set_tracer_provider_for_testing(provider)
    manager = _manager(load_tool_catalog(), profile="readonly")
    worker_context: dict[str, str | None] = {}

    def worker():
        worker_context["request_id"] = get_request_id()
        worker_context["trace_id"] = get_trace_id()
        return ["memory"]

    async def list_databases():
        return {"databases": await ArangoAgentBase.run_sync(worker)}

    manager.add_tool(list_databases, name="list-databases")
    try:
        result = await manager.call_tool("list-databases", {})
    finally:
        set_tracer_provider_for_testing(None)
    assert result["status"] == "success"
    spans = {span.name: span for span in exporter.get_finished_spans()}
    request = spans["mcp.request"]
    tool = spans["mcp.tool.call"]
    database = spans["arango.database"]
    assert tool.parent is not None and tool.parent.span_id == request.context.span_id
    assert database.parent is not None and database.parent.span_id == tool.context.span_id
    assert worker_context["request_id"]
    assert worker_context["trace_id"] == f"{request.context.trace_id:032x}"


@pytest.mark.asyncio
async def test_every_catalog_write_or_admin_attempt_has_one_redacted_audit(caplog):
    catalog = load_tool_catalog()
    manager = _manager(catalog)
    audited = {
        name
        for name, definition in catalog.tools.items()
        if definition.operation in {"write", "admin"}
    }
    secret_values = {
        "password": "raw-password-value",
        "token": "raw-token-value",
        "aql": "INSERT {secret:'raw-aql-value'} INTO docs",
        "payload": "raw-document-payload",
    }
    arguments = {
        "password": secret_values["password"],
        "access_token": secret_values["token"],
        "confirmation_token": secret_values["token"],
        "aql_query": secret_values["aql"],
        "document": {"secret": secret_values["payload"]},
        "database_name": "audit_db",
    }
    caplog.set_level("INFO", logger="audit.catalog")

    for name in sorted(audited):
        with pytest.raises(ToolError):
            await manager.call_tool(name, arguments)

    records = [record for record in caplog.records if hasattr(record, "audit_event")]
    assert len(records) == len(audited)
    assert {record.audit_event["action"] for record in records} == audited
    assert all(record.audit_event["outcome"] == "denied" for record in records)
    assert all(record.audit_event["actor"] == "local-stdio" for record in records)
    assert all(record.audit_event["correlation_id"] for record in records)
    serialized = "\n".join(record.getMessage() for record in records)
    assert all(value not in serialized for value in secret_values.values())


def test_confirmation_tokens_bind_actor_action_parameters_expiry_and_replay():
    secret = "operator-only-secret"
    arguments = {"collection_name": "users", "document_key_or_id": "42"}
    token = mint_confirmation_token(
        secret=secret,
        actor="alice",
        action="delete-document",
        arguments=arguments,
        ttl_seconds=60,
        now=1000,
    )
    verifier = ConfirmationVerifier(secret)
    claims = verifier.verify_and_consume(
        token,
        actor="alice",
        action="delete-document",
        arguments=arguments,
        now=1010,
    )
    assert claims.parameters_sha256 == canonical_parameters_hash(arguments)
    with pytest.raises(ConfirmationError, match="already been used"):
        verifier.verify_and_consume(
            token,
            actor="alice",
            action="delete-document",
            arguments=arguments,
            now=1011,
        )

    fresh = mint_confirmation_token(
        secret=secret,
        actor="alice",
        action="delete-document",
        arguments=arguments,
        ttl_seconds=10,
        now=1000,
    )
    with pytest.raises(ConfirmationError, match="expired"):
        ConfirmationVerifier(secret).verify_and_consume(
            fresh,
            actor="alice",
            action="delete-document",
            arguments=arguments,
            now=1010,
        )


@pytest.mark.asyncio
async def test_irreversible_tool_requires_out_of_band_token_and_rejects_replay():
    secret = "operator-only-secret"
    manager = _manager(load_tool_catalog(), confirmation_secret=secret)
    executed = 0

    async def delete_document(collection_name, document_key_or_id):
        nonlocal executed
        executed += 1
        return {"deleted": document_key_or_id, "collection": collection_name}

    manager.add_tool(delete_document, name="delete-document")
    arguments = {"collection_name": "users", "document_key_or_id": "42"}
    denied = await manager.call_tool("delete-document", arguments)
    assert denied["error"]["code"] == "confirmation_required"
    assert executed == 0

    token = mint_confirmation_token(
        secret=secret,
        actor="alice",
        action="delete-document",
        arguments=arguments,
    )
    with actor_scope("alice"):
        approved = await manager.call_tool(
            "delete-document", {**arguments, "confirmation_token": token}
        )
        replay = await manager.call_tool(
            "delete-document", {**arguments, "confirmation_token": token}
        )
    assert approved["status"] == "success"
    assert replay["error"]["code"] == "confirmation_replayed"
    assert executed == 1

    tool = manager.get_tool("delete-document")
    assert tool is not None
    assert "confirmation_token" in tool.parameters["required"]
