"""Interoperability contracts for MCP resources and safe workflow prompts."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("ARANGO_HOSTS", "http://localhost:8529")
os.environ.setdefault("ARANGO_ROOT_USERNAME", "root")
os.environ.setdefault("ARANGO_ROOT_PASSWORD", "test")

with patch("arangodb_mcp.arango_connector.ArangoClient"):
    from arangodb_mcp.server import mcp_app

from arangodb_mcp.mcp_content import (
    manual_resource,
    profile_resource,
    registered_content_inventory,
    schema_resource,
    status_resource,
)


@pytest.mark.asyncio
async def test_resources_and_prompts_have_exact_interoperable_inventory():
    inventory = registered_content_inventory()
    assert inventory == {
        "resources": [
            "arangodb://profile",
            "arangodb://schema",
            "arangodb://status",
        ],
        "templates": ["arangodb://manuals/{manual_name}"],
        "prompts": [
            "safe-aql-workflow",
            "safe-graph-workflow",
            "safe-search-workflow",
        ],
    }
    resources = await mcp_app.list_resources()
    templates = await mcp_app.list_resource_templates()
    prompts = await mcp_app.list_prompts()
    assert {str(resource.uri) for resource in resources} == set(inventory["resources"])
    assert {template.uriTemplate for template in templates} == set(inventory["templates"])
    assert {prompt.name for prompt in prompts} == set(inventory["prompts"])


@pytest.mark.asyncio
async def test_manual_resource_and_safe_aql_prompt_round_trip():
    contents = await mcp_app.read_resource("arangodb://manuals/aql_ref")
    assert "AQL" in contents[0].content
    assert "AQL" in manual_resource("aql_ref")
    prompt = await mcp_app.get_prompt(
        "safe-aql-workflow",
        {"task": "find active users", "database_name": "app"},
    )
    text = prompt.messages[0].content.text
    assert "validate-aql-query" in text
    assert "explain-aql-query" in text
    assert "out-of-band confirmation" in text


def test_profile_resource_reports_exact_active_inventory():
    profile = json.loads(profile_resource())
    assert profile["profile"] == "readonly"
    assert profile["tool_count"] == 17
    assert "list-databases" in profile["tools"]
    assert "create-document" not in profile["tools"]


@pytest.mark.asyncio
async def test_schema_and_status_resources_are_bounded_and_secret_free(monkeypatch):
    database = MagicMock()
    database.name = "app"
    database.collections.return_value = [
        {"name": "users", "type": 2, "status": 3, "isSystem": False}
    ]
    monkeypatch.setattr("arangodb_mcp.mcp_content.arango_connector.get_db", lambda: database)
    monkeypatch.setattr("arangodb_mcp.mcp_content.arango_connector.health_check", lambda: True)

    schema = json.loads(await schema_resource())
    status = json.loads(await status_resource())
    assert schema == {
        "database": "app",
        "collections": [{"name": "users", "type": 2, "status": 3, "system": False}],
        "truncated": False,
        "maximum": 1000,
    }
    assert status["database_ready"] is True
    assert status["protocol"] == "2026-07-28"
    assert "password" not in json.dumps(status).lower()
