"""Integration tests filling coverage gaps identified during review.

These tests require a running ArangoDB instance (via Docker or ARANGO_HOSTS).
They exercise document replace/bulk operations with data verification,
ArangoSearch view CRUD, additional index types, and hybrid search.
"""

import time

import pytest

from agents.document_crud_agent import DocumentCRUDAgent
from agents.index_management_agent import IndexManagementAgent
from agents.vector_search_agent import VectorSearchAgent
from agents.view_management_agent import ViewManagementAgent


def _requires_vector(vector_index_supported):
    if not vector_index_supported:
        pytest.skip("Vector indexes not available (requires 3.12.4+ with --vector-index)")


# ── Document Operations (data verification) ──────────────────────────


class TestDocumentOperationsVerified:
    """Verify document operations mutate data correctly, not just status codes."""

    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector, test_db, test_collection):
        self.agent = DocumentCRUDAgent()
        self.col = test_collection
        self.db = test_db

    @pytest.mark.asyncio
    async def test_replace_document(self):
        """Replace should remove old fields entirely, not merge."""
        created = await self.agent.arun(
            {
                "operation": "create_document",
                "collection_name": self.col,
                "document_data": {"old_field": "old_value", "shared": "original"},
            }
        )
        key = created["metadata"]["_key"]

        result = await self.agent.arun(
            {
                "operation": "replace_document",
                "collection_name": self.col,
                "document_data": {"_key": key, "new_field": "new_value"},
            }
        )
        assert "replaced" in result.get("status", "").lower()

        read_back = await self.agent.arun(
            {
                "operation": "read_document",
                "collection_name": self.col,
                "document_key_or_id": key,
            }
        )
        doc = read_back["document"]
        assert doc["new_field"] == "new_value"
        assert "old_field" not in doc, "Replace should remove fields not in the new document"
        assert "shared" not in doc

    @pytest.mark.asyncio
    async def test_update_documents_bulk(self):
        """Bulk update 2 of 3 docs and verify only those changed."""
        keys = []
        for i in range(3):
            r = await self.agent.arun(
                {
                    "operation": "create_document",
                    "collection_name": self.col,
                    "document_data": {"val": i, "tag": "bulk_update_test"},
                }
            )
            keys.append(r["metadata"]["_key"])

        result = await self.agent.arun(
            {
                "operation": "update_documents_bulk",
                "collection_name": self.col,
                "documents_data": [
                    {"_key": keys[0], "val": 100},
                    {"_key": keys[1], "val": 200},
                ],
            }
        )
        assert "error" not in result

        for idx, expected in [(0, 100), (1, 200), (2, 2)]:
            doc = (
                await self.agent.arun(
                    {
                        "operation": "read_document",
                        "collection_name": self.col,
                        "document_key_or_id": keys[idx],
                    }
                )
            )["document"]
            assert doc["val"] == expected, f"Doc {idx} should have val={expected}"

    @pytest.mark.asyncio
    async def test_delete_documents_bulk(self):
        """Bulk delete 2 of 3 docs and verify only 1 remains."""
        keys = []
        for i in range(3):
            r = await self.agent.arun(
                {
                    "operation": "create_document",
                    "collection_name": self.col,
                    "document_data": {"seq": i, "tag": "bulk_del_test"},
                }
            )
            keys.append(r["metadata"]["_key"])

        result = await self.agent.arun(
            {
                "operation": "delete_documents_bulk",
                "collection_name": self.col,
                "documents_data": [{"_key": keys[0]}, {"_key": keys[1]}],
            }
        )
        assert "error" not in result

        survivor = await self.agent.arun(
            {
                "operation": "read_document",
                "collection_name": self.col,
                "document_key_or_id": keys[2],
            }
        )
        assert "document" in survivor
        assert survivor["document"]["seq"] == 2

        for deleted_key in keys[:2]:
            gone = await self.agent.arun(
                {
                    "operation": "read_document",
                    "collection_name": self.col,
                    "document_key_or_id": deleted_key,
                }
            )
            assert "error" in gone, f"Doc {deleted_key} should have been deleted"

    @pytest.mark.asyncio
    async def test_read_documents_with_filter_pagination(self):
        """Read with limit and skip to verify pagination."""
        for i in range(5):
            await self.agent.arun(
                {
                    "operation": "create_document",
                    "collection_name": self.col,
                    "document_data": {"group": "pag_test", "seq": i},
                }
            )

        result = await self.agent.arun(
            {
                "operation": "read_documents_filter",
                "collection_name": self.col,
                "filters": {"group": "pag_test"},
                "limit": 2,
                "skip": 1,
            }
        )
        assert "error" not in result
        assert result["count"] == 2, "limit=2 should return exactly 2 docs"
        assert len(result["documents"]) == 2


# ── ArangoSearch View Operations ─────────────────────────────────────


class TestArangoSearchViews:
    """Test arangosearch-type view create / update / replace."""

    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector, test_db, test_collection, arango_version):
        major, minor = [int(x) for x in arango_version.split(".")[:2]]
        if major < 3 or (major == 3 and minor < 10):
            pytest.skip("ArangoSearch views require ArangoDB 3.10+")
        self.view_agent = ViewManagementAgent()
        self.col = test_collection
        self.db = test_db

        col_obj = test_db.collection(test_collection)
        col_obj.insert_many(
            [
                {"title": "Alpha document", "body": "First entry"},
                {"title": "Beta document", "body": "Second entry"},
            ]
        )

    @pytest.mark.asyncio
    async def test_create_arangosearch_view(self):
        result = await self.view_agent.arun(
            {
                "operation": "create_view",
                "view_name": "as_test_view",
                "view_type": "arangosearch",
                "properties": {
                    "links": {
                        self.col: {
                            "analyzers": ["identity"],
                            "includeAllFields": True,
                        }
                    }
                },
            }
        )
        assert "error" not in result, result
        assert "created" in result.get("status", "").lower()

        props = await self.view_agent.arun(
            {
                "operation": "get_view_properties",
                "view_name": "as_test_view",
            }
        )
        assert "error" not in props
        assert props["view_properties"]["type"] == "arangosearch"

        await self.view_agent.arun(
            {"operation": "delete_view", "view_name": "as_test_view"}
        )

    @pytest.mark.asyncio
    async def test_update_arangosearch_view(self):
        await self.view_agent.arun(
            {
                "operation": "create_view",
                "view_name": "as_update_view",
                "view_type": "arangosearch",
                "properties": {
                    "links": {
                        self.col: {
                            "analyzers": ["identity"],
                            "includeAllFields": True,
                        }
                    }
                },
            }
        )

        result = await self.view_agent.arun(
            {
                "operation": "update_view_properties",
                "view_name": "as_update_view",
                "properties": {
                    "links": {
                        self.col: {
                            "analyzers": ["identity", "text_en"],
                            "includeAllFields": True,
                        }
                    }
                },
            }
        )
        assert "error" not in result, result
        assert "updated" in result.get("status", "").lower()

        await self.view_agent.arun(
            {"operation": "delete_view", "view_name": "as_update_view"}
        )

    @pytest.mark.asyncio
    async def test_replace_arangosearch_view(self):
        await self.view_agent.arun(
            {
                "operation": "create_view",
                "view_name": "as_replace_view",
                "view_type": "arangosearch",
                "properties": {
                    "links": {
                        self.col: {
                            "analyzers": ["identity"],
                            "includeAllFields": True,
                        }
                    }
                },
            }
        )

        result = await self.view_agent.arun(
            {
                "operation": "replace_view_properties",
                "view_name": "as_replace_view",
                "properties": {
                    "links": {
                        self.col: {
                            "analyzers": ["text_en"],
                            "includeAllFields": False,
                            "fields": {"title": {}},
                        }
                    }
                },
            }
        )
        assert "error" not in result, result
        assert "replaced" in result.get("status", "").lower()

        await self.view_agent.arun(
            {"operation": "delete_view", "view_name": "as_replace_view"}
        )


# ── Index Types ──────────────────────────────────────────────────────


class TestIndexTypes:
    """Test geo, TTL, and MDI index creation."""

    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector, test_db, test_collection):
        self.agent = IndexManagementAgent()
        self.col = test_collection
        self.db = test_db

    @pytest.mark.asyncio
    async def test_create_geo_index(self):
        col_obj = self.db.collection(self.col)
        col_obj.insert({"location": [48.137154, 11.576124]})

        result = await self.agent.arun(
            {
                "operation": "create_index",
                "collection_name": self.col,
                "index_definition": {
                    "type": "geo",
                    "fields": ["location"],
                    "name": "geo_location_idx",
                },
            }
        )
        assert "error" not in result, result
        assert result["index_info"]["type"] == "geo"

        await self.agent.arun(
            {
                "operation": "delete_index",
                "collection_name": self.col,
                "index_id_or_name": "geo_location_idx",
            }
        )

    @pytest.mark.asyncio
    async def test_create_ttl_index(self):
        col_obj = self.db.collection(self.col)
        col_obj.insert({"createdAt": time.time()})

        result = await self.agent.arun(
            {
                "operation": "create_index",
                "collection_name": self.col,
                "index_definition": {
                    "type": "ttl",
                    "fields": ["createdAt"],
                    "expireAfter": 3600,
                    "name": "ttl_created_idx",
                },
            }
        )
        assert "error" not in result, result
        assert result["index_info"]["type"] == "ttl"

        await self.agent.arun(
            {
                "operation": "delete_index",
                "collection_name": self.col,
                "index_id_or_name": "ttl_created_idx",
            }
        )

    @pytest.mark.asyncio
    async def test_create_mdi_index(self, arango_version):
        major, minor = [int(x) for x in arango_version.split(".")[:2]]
        if major < 3 or (major == 3 and minor < 12):
            pytest.skip("MDI indexes require ArangoDB 3.12+")

        col_obj = self.db.collection(self.col)
        col_obj.insert({"x": 1.0, "y": 2.0})

        result = await self.agent.arun(
            {
                "operation": "create_index",
                "collection_name": self.col,
                "index_definition": {
                    "type": "mdi",
                    "fields": ["x", "y"],
                    "fieldValueTypes": "double",
                    "name": "mdi_xy_idx",
                },
            }
        )
        assert "error" not in result, result
        assert result["index_info"]["type"] == "mdi"

        await self.agent.arun(
            {
                "operation": "delete_index",
                "collection_name": self.col,
                "index_id_or_name": "mdi_xy_idx",
            }
        )


# ── Hybrid Search ────────────────────────────────────────────────────


class TestHybridSearch:
    """Test hybrid search combining vector + ArangoSearch text scoring."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        patch_connector,
        test_db,
        test_collection,
        vector_index_supported,
        arango_version,
    ):
        _requires_vector(vector_index_supported)
        major, minor = [int(x) for x in arango_version.split(".")[:2]]
        if major < 3 or (major == 3 and minor < 10):
            pytest.skip("Hybrid search requires ArangoSearch (3.10+)")

        self.vector_agent = VectorSearchAgent()
        self.view_agent = ViewManagementAgent()
        self.col = test_collection
        self.db = test_db

        col_obj = test_db.collection(test_collection)
        docs = [
            {
                "title": "Machine Learning Fundamentals",
                "embedding": [1.0, 0.0, 0.0],
            },
            {
                "title": "Deep Learning with Neural Networks",
                "embedding": [0.9, 0.1, 0.0],
            },
            {
                "title": "Italian Cooking Recipes",
                "embedding": [0.0, 0.0, 1.0],
            },
            {
                "title": "Advanced Machine Learning Techniques",
                "embedding": [0.95, 0.05, 0.0],
            },
        ]
        col_obj.insert_many(docs)

        col_obj.add_index(
            {
                "type": "vector",
                "fields": ["embedding"],
                "params": {"metric": "l2", "dimension": 3, "nLists": 1},
                "name": "hybrid_vec_idx",
            }
        )
        col_obj.add_index(
            {
                "type": "inverted",
                "fields": [{"name": "title"}],
                "name": "hybrid_inv_idx",
            }
        )

        self.view_name = "hybrid_test_view"
        test_db.create_view(
            name=self.view_name,
            view_type="search-alias",
            properties={
                "indexes": [
                    {"collection": test_collection, "index": "hybrid_inv_idx"}
                ]
            },
        )
        time.sleep(1)

    @pytest.mark.asyncio
    async def test_hybrid_search_with_text_and_vector(self):
        result = await self.vector_agent.arun(
            {
                "operation": "hybrid_search",
                "collection_name": self.col,
                "vector_field": "embedding",
                "query_vector": [1.0, 0.0, 0.0],
                "metric": "l2",
                "limit": 5,
                "text_field": "title",
                "text_query": "Machine Learning",
                "text_analyzer": "text_en",
                "view_name": self.view_name,
                "vector_weight": 0.5,
                "text_weight": 0.5,
            }
        )
        assert "error" not in result, result
        assert result["count"] > 0
        assert "aql_generated" in result
        first = result["results"][0]
        assert "vec_score" in first
        assert "text_score" in first
        assert "combined_score" in first

    @pytest.mark.asyncio
    async def test_hybrid_search_falls_back_to_vector_without_text_params(self):
        result = await self.vector_agent.arun(
            {
                "operation": "hybrid_search",
                "collection_name": self.col,
                "vector_field": "embedding",
                "query_vector": [1.0, 0.0, 0.0],
                "metric": "l2",
                "limit": 3,
            }
        )
        assert "error" not in result, result
        assert result["count"] > 0
        assert "aql_generated" in result
        assert "APPROX_NEAR_L2" in result["aql_generated"]
        assert "combined_score" not in result["results"][0]
