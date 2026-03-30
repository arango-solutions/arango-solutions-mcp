"""Tests for DatabaseManagementAgent, ManualManagementAgent, and AnalyzerManagementAgent."""

import contextlib

import pytest  # noqa: I001

from agents.analyzer_management_agent import AnalyzerManagementAgent
from agents.database_management_agent import DatabaseManagementAgent
from agents.manual_management_agent import ManualManagementAgent

# ── Database Agent ────────────────────────────────────────────────────


class TestDatabaseAgent:
    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector):
        self.agent = DatabaseManagementAgent()

    @pytest.mark.asyncio
    async def test_list_databases(self):
        result = await self.agent.arun({"operation": "list_databases"})
        assert "error" not in result
        assert isinstance(result.get("databases"), list)
        assert "_system" in result["databases"]

    @pytest.mark.asyncio
    async def test_create_and_delete_database(self, system_db):
        db_name = "mcp_test_create_db"
        # Cleanup in case it exists from a prior failed run
        with contextlib.suppress(Exception):
            system_db.delete_database(db_name, ignore_missing=True)

        result = await self.agent.arun(
            {
                "operation": "create_database",
                "database_name": db_name,
            }
        )
        assert "error" not in result
        assert "created" in result.get("status", "").lower()

        # Create again should report already exists
        result2 = await self.agent.arun(
            {
                "operation": "create_database",
                "database_name": db_name,
            }
        )
        assert "already exists" in result2.get("status", "").lower()

        # Delete
        result3 = await self.agent.arun(
            {
                "operation": "delete_database",
                "database_name": db_name,
            }
        )
        assert "error" not in result3
        assert "deleted" in result3.get("status", "").lower()

    @pytest.mark.asyncio
    async def test_create_database_missing_name(self):
        result = await self.agent.arun({"operation": "create_database"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_delete_nonexistent_database(self):
        result = await self.agent.arun(
            {
                "operation": "delete_database",
                "database_name": "nonexistent_db_xyz_12345",
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_delete_system_database_blocked(self):
        result = await self.agent.arun(
            {
                "operation": "delete_database",
                "database_name": "_system",
            }
        )
        assert "error" in result
        assert "_system" in result["error"]

    @pytest.mark.asyncio
    async def test_get_database_info(self):
        result = await self.agent.arun(
            {
                "operation": "get_database_info",
            }
        )
        assert "error" not in result
        assert "database_info" in result

    @pytest.mark.asyncio
    async def test_unknown_operation(self):
        result = await self.agent.arun({"operation": "bogus_op"})
        assert "error" in result


# ── Manual Agent ──────────────────────────────────────────────────────


class TestManualAgent:
    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector, monkeypatch):
        self.agent = ManualManagementAgent()
        # Ensure working directory is project root so manuals/ is accessible
        import os

        monkeypatch.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    @pytest.mark.asyncio
    async def test_get_aql_ref_manual(self):
        result = await self.agent.arun(
            {
                "operation": "get_aql_manual",
                "manual_name": "aql_ref",
            }
        )
        assert "error" not in result
        assert "manual_content" in result
        assert len(result["manual_content"]) > 100

    @pytest.mark.asyncio
    async def test_get_optimization_manual(self):
        result = await self.agent.arun(
            {
                "operation": "get_aql_manual",
                "manual_name": "optimization",
            }
        )
        assert "error" not in result
        assert "manual_content" in result

    @pytest.mark.asyncio
    async def test_get_cypher2aql_manual(self):
        result = await self.agent.arun(
            {
                "operation": "get_aql_manual",
                "manual_name": "cypher2aql",
            }
        )
        assert "error" not in result
        assert "manual_content" in result

    @pytest.mark.asyncio
    async def test_unknown_manual_name(self):
        result = await self.agent.arun(
            {
                "operation": "get_aql_manual",
                "manual_name": "nonexistent",
            }
        )
        assert "error" in result
        assert "unknown manual" in result["error"].lower() or "available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_unknown_operation(self):
        result = await self.agent.arun({"operation": "bogus_op"})
        assert "error" in result


# ── Analyzer Agent ────────────────────────────────────────────────────


class TestAnalyzerAgent:
    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector):
        self.agent = AnalyzerManagementAgent()

    @pytest.mark.asyncio
    async def test_list_analyzers(self):
        result = await self.agent.arun({"operation": "list_analyzers"})
        assert "error" not in result
        assert isinstance(result.get("analyzers"), list)

    @pytest.mark.asyncio
    async def test_create_and_delete_analyzer(self):
        result = await self.agent.arun(
            {
                "operation": "create_analyzer",
                "analyzer_name": "test_text_analyzer",
                "analyzer_type": "text",
                "properties": {"locale": "en", "stemming": True},
                "features": ["frequency", "norm", "position"],
            }
        )
        assert "error" not in result
        assert "created" in result.get("status", "").lower()

        # Get properties
        props_result = await self.agent.arun(
            {
                "operation": "get_analyzer_properties",
                "analyzer_name": "test_text_analyzer",
            }
        )
        assert "error" not in props_result
        assert "analyzer_definition" in props_result

        # Delete
        del_result = await self.agent.arun(
            {
                "operation": "delete_analyzer",
                "analyzer_name": "test_text_analyzer",
            }
        )
        assert "error" not in del_result
        assert "deleted" in del_result.get("status", "").lower()

    @pytest.mark.asyncio
    async def test_create_analyzer_missing_name(self):
        result = await self.agent.arun(
            {
                "operation": "create_analyzer",
                "analyzer_type": "text",
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_analyzer_missing_type(self):
        result = await self.agent.arun(
            {
                "operation": "create_analyzer",
                "analyzer_name": "test_analyzer_no_type",
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_ngram_missing_params(self):
        result = await self.agent.arun(
            {
                "operation": "create_analyzer",
                "analyzer_name": "test_bad_ngram",
                "analyzer_type": "ngram",
                "properties": {"streamType": "utf8"},
            }
        )
        assert "error" in result
        assert "minN" in result["error"] or "maxN" in result["error"]

    @pytest.mark.asyncio
    async def test_delete_nonexistent_analyzer(self):
        result = await self.agent.arun(
            {
                "operation": "delete_analyzer",
                "analyzer_name": "nonexistent_analyzer_xyz",
            }
        )
        # ignore_missing=True means this returns success-ish
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_unknown_operation(self):
        result = await self.agent.arun({"operation": "bogus_op"})
        assert "error" in result
