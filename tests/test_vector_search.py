"""Tests for vector index creation, ANN search, and search-alias views.

Vector tests require ArangoDB 3.12.4+ started with --vector-index.
They are skipped automatically if the feature is unavailable.
"""

import math

import pytest

from agents.index_management_agent import IndexManagementAgent
from agents.vector_search_agent import VectorSearchAgent
from agents.view_management_agent import ViewManagementAgent


def _requires_vector(vector_index_supported):
    if not vector_index_supported:
        pytest.skip("Vector indexes not available (requires 3.12.4+ with --vector-index)")


# ── Vector Index Creation ─────────────────────────────────────────────


class TestVectorIndex:
    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector, test_db, test_collection, vector_index_supported):
        _requires_vector(vector_index_supported)
        self.index_agent = IndexManagementAgent()
        self.col = test_collection
        self.db = test_db
        # Populate with vector data before index creation
        col_obj = test_db.collection(test_collection)
        for i in range(20):
            angle = 2 * math.pi * i / 20
            col_obj.insert(
                {
                    "embedding": [math.cos(angle), math.sin(angle), float(i) / 20],
                    "label": f"item_{i}",
                    "category": "A" if i % 2 == 0 else "B",
                }
            )

    @pytest.mark.asyncio
    async def test_create_vector_index_l2(self):
        result = await self.index_agent.arun(
            {
                "operation": "create_index",
                "collection_name": self.col,
                "index_definition": {
                    "type": "vector",
                    "fields": ["embedding"],
                    "params": {
                        "metric": "l2",
                        "dimension": 3,
                        "nLists": 2,
                    },
                    "name": "test_vec_l2",
                },
            }
        )
        assert "error" not in result, result
        assert result["index_info"]["type"] == "vector"

    @pytest.mark.asyncio
    async def test_create_vector_index_cosine(self):
        result = await self.index_agent.arun(
            {
                "operation": "create_index",
                "collection_name": self.col,
                "index_definition": {
                    "type": "vector",
                    "fields": ["embedding"],
                    "params": {
                        "metric": "cosine",
                        "dimension": 3,
                        "nLists": 2,
                    },
                    "name": "test_vec_cos",
                },
            }
        )
        assert "error" not in result, result
        assert result["index_info"]["type"] == "vector"

    @pytest.mark.asyncio
    async def test_vector_index_listed(self):
        await self.index_agent.arun(
            {
                "operation": "create_index",
                "collection_name": self.col,
                "index_definition": {
                    "type": "vector",
                    "fields": ["embedding"],
                    "params": {"metric": "l2", "dimension": 3, "nLists": 2},
                    "name": "vec_list_test",
                },
            }
        )
        listing = await self.index_agent.arun(
            {
                "operation": "list_indexes",
                "collection_name": self.col,
            }
        )
        types = [idx["type"] for idx in listing["indexes"]]
        assert "vector" in types

    @pytest.mark.asyncio
    async def test_vector_index_delete(self):
        await self.index_agent.arun(
            {
                "operation": "create_index",
                "collection_name": self.col,
                "index_definition": {
                    "type": "vector",
                    "fields": ["embedding"],
                    "params": {"metric": "l2", "dimension": 3, "nLists": 2},
                    "name": "vec_del_test",
                },
            }
        )
        result = await self.index_agent.arun(
            {
                "operation": "delete_index",
                "collection_name": self.col,
                "index_id_or_name": "vec_del_test",
            }
        )
        assert "deleted" in result.get("status", "").lower()


# ── Vector Search Agent ───────────────────────────────────────────────


class TestVectorSearch:
    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector, test_db, test_collection, vector_index_supported):
        _requires_vector(vector_index_supported)
        self.agent = VectorSearchAgent()
        self.col = test_collection
        self.db = test_db

        col_obj = test_db.collection(test_collection)
        for i in range(20):
            angle = 2 * math.pi * i / 20
            col_obj.insert(
                {
                    "embedding": [math.cos(angle), math.sin(angle), float(i) / 20],
                    "label": f"item_{i}",
                    "category": "A" if i % 2 == 0 else "B",
                }
            )

        col_obj.add_index(
            {
                "type": "vector",
                "fields": ["embedding"],
                "params": {"metric": "l2", "dimension": 3, "nLists": 2},
                "name": "search_vec_idx",
            }
        )

    @pytest.mark.asyncio
    async def test_basic_vector_search(self):
        result = await self.agent.arun(
            {
                "operation": "vector_search",
                "collection_name": self.col,
                "vector_field": "embedding",
                "query_vector": [1.0, 0.0, 0.0],
                "metric": "l2",
                "limit": 5,
            }
        )
        assert "error" not in result, result
        assert result["count"] <= 5
        assert result["count"] > 0
        assert "similarity" in result["results"][0]

    @pytest.mark.asyncio
    async def test_vector_search_with_return_fields(self):
        result = await self.agent.arun(
            {
                "operation": "vector_search",
                "collection_name": self.col,
                "vector_field": "embedding",
                "query_vector": [1.0, 0.0, 0.0],
                "metric": "l2",
                "limit": 3,
                "return_fields": ["label", "category"],
            }
        )
        assert "error" not in result, result
        first = result["results"][0]
        assert "label" in first
        assert "category" in first
        assert "embedding" not in first

    @pytest.mark.asyncio
    async def test_vector_search_no_similarity(self):
        result = await self.agent.arun(
            {
                "operation": "vector_search",
                "collection_name": self.col,
                "vector_field": "embedding",
                "query_vector": [1.0, 0.0, 0.0],
                "metric": "l2",
                "limit": 3,
                "include_similarity": False,
            }
        )
        assert "error" not in result, result
        assert "similarity" not in result["results"][0]

    @pytest.mark.asyncio
    async def test_vector_search_with_n_probe(self):
        result = await self.agent.arun(
            {
                "operation": "vector_search",
                "collection_name": self.col,
                "vector_field": "embedding",
                "query_vector": [0.0, 1.0, 0.5],
                "metric": "l2",
                "limit": 5,
                "n_probe": 2,
            }
        )
        assert "error" not in result, result
        assert result["count"] > 0

    @pytest.mark.asyncio
    async def test_vector_search_missing_collection(self):
        result = await self.agent.arun(
            {
                "operation": "vector_search",
                "collection_name": "",
                "vector_field": "embedding",
                "query_vector": [1.0],
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_vector_search_missing_vector(self):
        result = await self.agent.arun(
            {
                "operation": "vector_search",
                "collection_name": self.col,
                "vector_field": "embedding",
                "query_vector": [],
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_vector_search_invalid_metric(self):
        result = await self.agent.arun(
            {
                "operation": "vector_search",
                "collection_name": self.col,
                "vector_field": "embedding",
                "query_vector": [1.0, 0.0, 0.0],
                "metric": "manhattan",
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_vector_search_aql_returned(self):
        """Verify the generated AQL is included in the response."""
        result = await self.agent.arun(
            {
                "operation": "vector_search",
                "collection_name": self.col,
                "vector_field": "embedding",
                "query_vector": [1.0, 0.0, 0.0],
                "metric": "l2",
                "limit": 3,
            }
        )
        assert "error" not in result, result
        assert "APPROX_NEAR_L2" in result["aql_generated"]

    @pytest.mark.asyncio
    async def test_unknown_operation(self):
        result = await self.agent.arun({"operation": "bogus"})
        assert "error" in result


# ── Search-Alias View Agent ──────────────────────────────────────────


class TestSearchAliasView:
    """Test search-alias views backed by inverted indexes."""

    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector, test_db, test_collection, arango_version):
        major, minor = [int(x) for x in arango_version.split(".")[:2]]
        if major < 3 or (major == 3 and minor < 10):
            pytest.skip("Inverted indexes and search-alias views require 3.10+")
        self.view_agent = ViewManagementAgent()
        self.col = test_collection
        self.db = test_db

        col_obj = test_db.collection(test_collection)
        col_obj.insert_many(
            [
                {"title": "Introduction to Machine Learning", "body": "ML basics"},
                {"title": "Deep Learning with Neural Networks", "body": "DL tutorial"},
                {"title": "Cooking Italian Pasta", "body": "Recipes"},
            ]
        )
        col_obj.add_index(
            {
                "type": "inverted",
                "fields": [{"name": "title"}, {"name": "body"}],
                "name": "inv_title_body",
            }
        )

    @pytest.mark.asyncio
    async def test_create_search_alias_view(self):
        result = await self.view_agent.arun(
            {
                "operation": "create_view",
                "view_name": "alias_test_view",
                "view_type": "search-alias",
                "properties": {
                    "indexes": [
                        {
                            "collection": self.col,
                            "index": "inv_title_body",
                        }
                    ]
                },
            }
        )
        assert "error" not in result, result
        assert "created" in result.get("status", "").lower()

    @pytest.mark.asyncio
    async def test_search_alias_requires_indexes(self):
        result = await self.view_agent.arun(
            {
                "operation": "create_view",
                "view_name": "bad_alias_view",
                "view_type": "search-alias",
                "properties": {},
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_alias_get_properties(self):
        await self.view_agent.arun(
            {
                "operation": "create_view",
                "view_name": "props_alias_view",
                "view_type": "search-alias",
                "properties": {
                    "indexes": [
                        {
                            "collection": self.col,
                            "index": "inv_title_body",
                        }
                    ]
                },
            }
        )
        result = await self.view_agent.arun(
            {
                "operation": "get_view_properties",
                "view_name": "props_alias_view",
            }
        )
        assert "error" not in result
        assert "view_properties" in result

    @pytest.mark.asyncio
    async def test_search_alias_aql_query(self):
        """Verify we can query through a search-alias view via AQL."""
        await self.view_agent.arun(
            {
                "operation": "create_view",
                "view_name": "query_alias_view",
                "view_type": "search-alias",
                "properties": {
                    "indexes": [
                        {
                            "collection": self.col,
                            "index": "inv_title_body",
                        }
                    ]
                },
            }
        )
        from agents.aql_execution_agent import AQLExecutionAgent

        aql_agent = AQLExecutionAgent()

        # Allow a short delay for the view to be ready
        import time

        time.sleep(1)

        result = await aql_agent.arun(
            {
                "aql_query": (
                    "FOR doc IN query_alias_view "
                    "SEARCH doc.title == 'Cooking Italian Pasta' "
                    "RETURN doc.title"
                ),
            }
        )
        assert "error" not in result, result
        assert "Cooking Italian Pasta" in result["results"]

    @pytest.mark.asyncio
    async def test_delete_search_alias_view(self):
        await self.view_agent.arun(
            {
                "operation": "create_view",
                "view_name": "del_alias_view",
                "view_type": "search-alias",
                "properties": {
                    "indexes": [
                        {
                            "collection": self.col,
                            "index": "inv_title_body",
                        }
                    ]
                },
            }
        )
        result = await self.view_agent.arun(
            {
                "operation": "delete_view",
                "view_name": "del_alias_view",
            }
        )
        assert "deleted" in result.get("status", "").lower()
