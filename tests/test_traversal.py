"""Tests for graph traversal agent and AQL explain/validate operations.

These tests build a small graph (users connected by 'follows' edges)
and test traversal, shortest path, k-shortest paths, and neighbor queries.
"""

import pytest
from arango.database import StandardDatabase

from agents.aql_execution_agent import AQLExecutionAgent
from agents.graph_traversal_agent import GraphTraversalAgent

# ── Graph Traversal Agent ─────────────────────────────────────────────


class TestGraphTraversal:
    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector, test_db: StandardDatabase):
        self.agent = GraphTraversalAgent()
        self.db = test_db

        # Build a small social graph:
        #   alice -> bob -> charlie -> dave
        #             \-> eve
        test_db.create_collection("users")
        test_db.create_collection("follows", edge=True)

        users = test_db.collection("users")
        users.insert_many(
            [
                {"_key": "alice", "name": "Alice", "role": "admin"},
                {"_key": "bob", "name": "Bob", "role": "user"},
                {"_key": "charlie", "name": "Charlie", "role": "user"},
                {"_key": "dave", "name": "Dave", "role": "admin"},
                {"_key": "eve", "name": "Eve", "role": "user"},
            ]
        )

        follows = test_db.collection("follows")
        follows.insert_many(
            [
                {"_from": "users/alice", "_to": "users/bob", "weight": 1},
                {"_from": "users/bob", "_to": "users/charlie", "weight": 2},
                {"_from": "users/bob", "_to": "users/eve", "weight": 1},
                {"_from": "users/charlie", "_to": "users/dave", "weight": 3},
            ]
        )

        test_db.create_graph(
            "social",
            edge_definitions=[
                {
                    "edge_collection": "follows",
                    "from_vertex_collections": ["users"],
                    "to_vertex_collections": ["users"],
                }
            ],
        )

    # ── Traverse ──

    @pytest.mark.asyncio
    async def test_traverse_outbound_depth_1(self):
        result = await self.agent.arun(
            {
                "operation": "traverse",
                "start_vertex": "users/alice",
                "graph_name": "social",
                "direction": "OUTBOUND",
                "min_depth": 1,
                "max_depth": 1,
            }
        )
        assert "error" not in result, result
        names = [r["vertex"]["name"] for r in result["results"]]
        assert "Bob" in names
        assert len(names) == 1

    @pytest.mark.asyncio
    async def test_traverse_outbound_depth_2(self):
        result = await self.agent.arun(
            {
                "operation": "traverse",
                "start_vertex": "users/alice",
                "graph_name": "social",
                "direction": "OUTBOUND",
                "min_depth": 1,
                "max_depth": 2,
            }
        )
        assert "error" not in result, result
        names = [r["vertex"]["name"] for r in result["results"]]
        assert "Bob" in names
        assert "Charlie" in names or "Eve" in names

    @pytest.mark.asyncio
    async def test_traverse_inbound(self):
        result = await self.agent.arun(
            {
                "operation": "traverse",
                "start_vertex": "users/bob",
                "graph_name": "social",
                "direction": "INBOUND",
                "min_depth": 1,
                "max_depth": 1,
            }
        )
        assert "error" not in result, result
        names = [r["vertex"]["name"] for r in result["results"]]
        assert "Alice" in names

    @pytest.mark.asyncio
    async def test_traverse_any_direction(self):
        result = await self.agent.arun(
            {
                "operation": "traverse",
                "start_vertex": "users/bob",
                "graph_name": "social",
                "direction": "ANY",
                "min_depth": 1,
                "max_depth": 1,
            }
        )
        assert "error" not in result, result
        assert result["count"] >= 3  # alice, charlie, eve

    @pytest.mark.asyncio
    async def test_traverse_with_edge_collections(self):
        result = await self.agent.arun(
            {
                "operation": "traverse",
                "start_vertex": "users/alice",
                "edge_collections": ["follows"],
                "direction": "OUTBOUND",
                "min_depth": 1,
                "max_depth": 1,
            }
        )
        assert "error" not in result, result
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_traverse_with_vertex_filter(self):
        result = await self.agent.arun(
            {
                "operation": "traverse",
                "start_vertex": "users/alice",
                "graph_name": "social",
                "direction": "OUTBOUND",
                "min_depth": 1,
                "max_depth": 3,
                "vertex_filters": {"role": "admin"},
            }
        )
        assert "error" not in result, result
        for r in result["results"]:
            assert r["vertex"]["role"] == "admin"

    @pytest.mark.asyncio
    async def test_traverse_return_paths(self):
        result = await self.agent.arun(
            {
                "operation": "traverse",
                "start_vertex": "users/alice",
                "graph_name": "social",
                "direction": "OUTBOUND",
                "min_depth": 1,
                "max_depth": 2,
                "return_paths": True,
            }
        )
        assert "error" not in result, result
        assert "path" in result["results"][0]

    @pytest.mark.asyncio
    async def test_traverse_aql_generated(self):
        result = await self.agent.arun(
            {
                "operation": "traverse",
                "start_vertex": "users/alice",
                "graph_name": "social",
                "direction": "OUTBOUND",
                "min_depth": 1,
                "max_depth": 1,
            }
        )
        assert "aql_generated" in result
        assert "OUTBOUND" in result["aql_generated"]
        assert "GRAPH 'social'" in result["aql_generated"]

    @pytest.mark.asyncio
    async def test_traverse_missing_start(self):
        result = await self.agent.arun(
            {
                "operation": "traverse",
                "start_vertex": "",
                "graph_name": "social",
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_traverse_invalid_direction(self):
        result = await self.agent.arun(
            {
                "operation": "traverse",
                "start_vertex": "users/alice",
                "graph_name": "social",
                "direction": "SIDEWAYS",
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_traverse_no_graph_source(self):
        result = await self.agent.arun(
            {
                "operation": "traverse",
                "start_vertex": "users/alice",
                "direction": "OUTBOUND",
            }
        )
        assert "error" in result

    # ── Shortest Path ──

    @pytest.mark.asyncio
    async def test_shortest_path(self):
        result = await self.agent.arun(
            {
                "operation": "shortest_path",
                "start_vertex": "users/alice",
                "target_vertex": "users/dave",
                "graph_name": "social",
                "direction": "OUTBOUND",
            }
        )
        assert "error" not in result, result
        assert result["path_length"] == 3  # alice -> bob -> charlie -> dave
        keys = [r["vertex"]["_key"] for r in result["results"]]
        assert keys[0] == "alice"
        assert keys[-1] == "dave"

    @pytest.mark.asyncio
    async def test_shortest_path_weighted(self):
        result = await self.agent.arun(
            {
                "operation": "shortest_path",
                "start_vertex": "users/alice",
                "target_vertex": "users/dave",
                "graph_name": "social",
                "direction": "OUTBOUND",
                "weight_attribute": "weight",
            }
        )
        assert "error" not in result, result
        assert result["path_length"] >= 1

    @pytest.mark.asyncio
    async def test_shortest_path_no_path(self):
        result = await self.agent.arun(
            {
                "operation": "shortest_path",
                "start_vertex": "users/dave",
                "target_vertex": "users/alice",
                "graph_name": "social",
                "direction": "OUTBOUND",
            }
        )
        assert "error" not in result
        assert result["path_length"] == 0

    @pytest.mark.asyncio
    async def test_shortest_path_missing_target(self):
        result = await self.agent.arun(
            {
                "operation": "shortest_path",
                "start_vertex": "users/alice",
                "target_vertex": "",
                "graph_name": "social",
            }
        )
        assert "error" in result

    # ── K Shortest Paths ──

    @pytest.mark.asyncio
    async def test_k_shortest_paths(self):
        result = await self.agent.arun(
            {
                "operation": "k_shortest_paths",
                "start_vertex": "users/alice",
                "target_vertex": "users/dave",
                "graph_name": "social",
                "direction": "OUTBOUND",
                "limit": 3,
            }
        )
        assert "error" not in result, result
        assert result["count"] >= 1

    # ── Neighbors ──

    @pytest.mark.asyncio
    async def test_neighbors_any(self):
        result = await self.agent.arun(
            {
                "operation": "neighbors",
                "start_vertex": "users/bob",
                "graph_name": "social",
                "direction": "ANY",
                "depth": 1,
            }
        )
        assert "error" not in result, result
        keys = [r["_key"] for r in result["results"]]
        assert "alice" in keys
        assert "charlie" in keys or "eve" in keys

    @pytest.mark.asyncio
    async def test_neighbors_outbound(self):
        result = await self.agent.arun(
            {
                "operation": "neighbors",
                "start_vertex": "users/bob",
                "graph_name": "social",
                "direction": "OUTBOUND",
            }
        )
        assert "error" not in result, result
        keys = [r["_key"] for r in result["results"]]
        assert "charlie" in keys
        assert "eve" in keys
        assert "alice" not in keys

    @pytest.mark.asyncio
    async def test_neighbors_with_filter(self):
        result = await self.agent.arun(
            {
                "operation": "neighbors",
                "start_vertex": "users/alice",
                "graph_name": "social",
                "direction": "OUTBOUND",
                "depth": 3,
                "vertex_filters": {"role": "admin"},
            }
        )
        assert "error" not in result, result
        for r in result["results"]:
            assert r["role"] == "admin"

    @pytest.mark.asyncio
    async def test_unknown_operation(self):
        result = await self.agent.arun({"operation": "bogus_traversal"})
        assert "error" in result


# ── AQL Explain & Validate ────────────────────────────────────────────


class TestAQLExplainValidate:
    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector, test_db, test_collection):
        self.agent = AQLExecutionAgent()
        self.col = test_collection

    @pytest.mark.asyncio
    async def test_explain_simple_query(self):
        result = await self.agent.arun(
            {
                "operation": "explain",
                "aql_query": "RETURN 1",
            }
        )
        assert "error" not in result, result
        assert "plan" in result

    @pytest.mark.asyncio
    async def test_explain_collection_query(self):
        result = await self.agent.arun(
            {
                "operation": "explain",
                "aql_query": f"FOR doc IN `{self.col}` RETURN doc",
            }
        )
        assert "error" not in result, result
        plan = result["plan"]
        assert "nodes" in plan or "rules" in plan

    @pytest.mark.asyncio
    async def test_explain_with_bind_vars(self):
        result = await self.agent.arun(
            {
                "operation": "explain",
                "aql_query": "FOR i IN 1..@n RETURN i",
                "bind_vars": {"n": 10},
            }
        )
        assert "error" not in result, result

    @pytest.mark.asyncio
    async def test_explain_bad_query(self):
        result = await self.agent.arun(
            {
                "operation": "explain",
                "aql_query": "THIS IS NOT AQL",
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_validate_valid_query(self):
        result = await self.agent.arun(
            {
                "operation": "validate",
                "aql_query": "FOR doc IN users RETURN doc",
            }
        )
        assert "error" not in result, result
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_invalid_query(self):
        result = await self.agent.arun(
            {
                "operation": "validate",
                "aql_query": "GIBBERISH QUERY SYNTAX",
            }
        )
        assert result["valid"] is False

    @pytest.mark.asyncio
    async def test_explain_empty_query(self):
        result = await self.agent.arun(
            {
                "operation": "explain",
                "aql_query": "",
            }
        )
        assert "error" in result
