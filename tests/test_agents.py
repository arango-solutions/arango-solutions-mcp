"""Tests for agent classes through their public arun() interface.

These tests hit a real ArangoDB instance via the patched connector, validating
that agents produce correct results against an ephemeral test database.
"""

import pytest
from arango.database import StandardDatabase

from agents.collection_management_agent import CollectionManagementAgent
from agents.document_crud_agent import DocumentCRUDAgent
from agents.index_management_agent import IndexManagementAgent
from agents.aql_execution_agent import AQLExecutionAgent


# ── Collection Agent ──────────────────────────────────────────────────

class TestCollectionAgent:
    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector):
        self.agent = CollectionManagementAgent()

    @pytest.mark.asyncio
    async def test_list_collections_empty(self):
        result = await self.agent.arun({"operation": "list_collections"})
        assert "error" not in result
        assert isinstance(result.get("collections"), list)

    @pytest.mark.asyncio
    async def test_create_and_list(self):
        result = await self.agent.arun({
            "operation": "create_collection",
            "collection_name": "agent_test_col",
            "collection_type": "document",
        })
        assert "error" not in result, result
        assert "created" in result.get("status", "").lower()

        listing = await self.agent.arun({"operation": "list_collections"})
        names = [c["name"] for c in listing["collections"]]
        assert "agent_test_col" in names

    @pytest.mark.asyncio
    async def test_create_duplicate_is_safe(self):
        await self.agent.arun({
            "operation": "create_collection",
            "collection_name": "dup_col",
        })
        result = await self.agent.arun({
            "operation": "create_collection",
            "collection_name": "dup_col",
        })
        assert "already exists" in result.get("status", "").lower()

    @pytest.mark.asyncio
    async def test_get_properties(self):
        await self.agent.arun({
            "operation": "create_collection",
            "collection_name": "props_col",
        })
        result = await self.agent.arun({
            "operation": "get_collection_properties",
            "collection_name": "props_col",
        })
        assert "error" not in result
        assert "properties" in result

    @pytest.mark.asyncio
    async def test_delete_collection(self):
        await self.agent.arun({
            "operation": "create_collection",
            "collection_name": "del_col",
        })
        result = await self.agent.arun({
            "operation": "delete_collection",
            "collection_name": "del_col",
        })
        assert "deleted" in result.get("status", "").lower()


# ── Document Agent ────────────────────────────────────────────────────

class TestDocumentAgent:
    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector, test_collection):
        self.agent = DocumentCRUDAgent()
        self.col = test_collection

    @pytest.mark.asyncio
    async def test_create_document(self):
        result = await self.agent.arun({
            "operation": "create_document",
            "collection_name": self.col,
            "document_data": {"name": "test_user", "age": 25},
        })
        assert "error" not in result
        assert result["metadata"]["_key"]

    @pytest.mark.asyncio
    async def test_read_document(self):
        created = await self.agent.arun({
            "operation": "create_document",
            "collection_name": self.col,
            "document_data": {"color": "blue"},
        })
        key = created["metadata"]["_key"]
        result = await self.agent.arun({
            "operation": "read_document",
            "collection_name": self.col,
            "document_key_or_id": key,
        })
        assert result["document"]["color"] == "blue"

    @pytest.mark.asyncio
    async def test_update_document(self):
        created = await self.agent.arun({
            "operation": "create_document",
            "collection_name": self.col,
            "document_data": {"status": "draft"},
        })
        key = created["metadata"]["_key"]
        result = await self.agent.arun({
            "operation": "update_document",
            "collection_name": self.col,
            "document_data": {"_key": key, "status": "published"},
        })
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_delete_document(self):
        created = await self.agent.arun({
            "operation": "create_document",
            "collection_name": self.col,
            "document_data": {"temp": True},
        })
        key = created["metadata"]["_key"]
        result = await self.agent.arun({
            "operation": "delete_document",
            "collection_name": self.col,
            "document_key_or_id": key,
        })
        assert "deleted" in result.get("status", "").lower()

    @pytest.mark.asyncio
    async def test_replace_document(self):
        created = await self.agent.arun({
            "operation": "create_document",
            "collection_name": self.col,
            "document_data": {"old_field": True, "keep": False},
        })
        key = created["metadata"]["_key"]
        result = await self.agent.arun({
            "operation": "replace_document",
            "collection_name": self.col,
            "document_data": {"_key": key, "new_field": "yes"},
        })
        assert "replaced" in result.get("status", "").lower()

    @pytest.mark.asyncio
    async def test_read_documents_filter(self):
        for i in range(3):
            await self.agent.arun({
                "operation": "create_document",
                "collection_name": self.col,
                "document_data": {"group": "A", "seq": i},
            })
        await self.agent.arun({
            "operation": "create_document",
            "collection_name": self.col,
            "document_data": {"group": "B", "seq": 99},
        })
        result = await self.agent.arun({
            "operation": "read_documents_filter",
            "collection_name": self.col,
            "filters": {"group": "A"},
        })
        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_upsert_insert(self):
        result = await self.agent.arun({
            "operation": "upsert_document",
            "collection_name": self.col,
            "search_fields": {"email": "new@example.com"},
            "document_data": {"email": "new@example.com", "name": "New User"},
        })
        assert "error" not in result
        assert result["was_insert"] is True
        assert result["document"]["name"] == "New User"

    @pytest.mark.asyncio
    async def test_upsert_update(self):
        await self.agent.arun({
            "operation": "create_document",
            "collection_name": self.col,
            "document_data": {"email": "existing@example.com", "visits": 1},
        })
        result = await self.agent.arun({
            "operation": "upsert_document",
            "collection_name": self.col,
            "search_fields": {"email": "existing@example.com"},
            "document_data": {"email": "existing@example.com", "visits": 1},
            "update_data": {"visits": 2, "returning": True},
        })
        assert "error" not in result
        assert result["was_insert"] is False
        assert result["document"]["visits"] == 2
        assert result["document"]["returning"] is True

    @pytest.mark.asyncio
    async def test_update_documents_bulk(self):
        keys = []
        for i in range(3):
            r = await self.agent.arun({
                "operation": "create_document",
                "collection_name": self.col,
                "document_data": {"batch": True, "val": i},
            })
            keys.append(r["metadata"]["_key"])

        result = await self.agent.arun({
            "operation": "update_documents_bulk",
            "collection_name": self.col,
            "documents_data": [{"_key": k, "val": 99} for k in keys],
        })
        assert "error" not in result
        assert "results" in result

    @pytest.mark.asyncio
    async def test_delete_documents_bulk(self):
        keys = []
        for i in range(3):
            r = await self.agent.arun({
                "operation": "create_document",
                "collection_name": self.col,
                "document_data": {"to_delete": True, "seq": i},
            })
            keys.append(r["metadata"]["_key"])

        result = await self.agent.arun({
            "operation": "delete_documents_bulk",
            "collection_name": self.col,
            "documents_data": [{"_key": k} for k in keys],
        })
        assert "error" not in result
        assert "results" in result

    @pytest.mark.asyncio
    async def test_missing_collection_error(self):
        result = await self.agent.arun({
            "operation": "create_document",
            "collection_name": "nonexistent_col_xyz",
            "document_data": {"x": 1},
        })
        assert "error" in result


# ── Collection Agent: Sharding Parameters ─────────────────────────────

class TestCollectionShardingAgent:
    """Test that sharding parameters are passed through to ArangoDB.

    On a single-server deployment, ArangoDB accepts sharding params
    but treats them as metadata. These tests verify the agent passes
    them correctly.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector):
        self.agent = CollectionManagementAgent()

    @pytest.mark.asyncio
    async def test_create_with_shard_keys(self):
        """Verify shard params are accepted without error.

        On single-server, ArangoDB silently accepts these params but doesn't
        reflect them in properties. Actual shard verification happens in
        test_cluster.py against a real cluster.
        """
        result = await self.agent.arun({
            "operation": "create_collection",
            "collection_name": "sharded_col",
            "collection_type": "document",
            "number_of_shards": 3,
            "shard_keys": ["region"],
        })
        assert "error" not in result, result
        assert "created" in result.get("status", "").lower()

    @pytest.mark.asyncio
    async def test_create_with_replication_factor(self):
        result = await self.agent.arun({
            "operation": "create_collection",
            "collection_name": "replicated_col",
            "number_of_shards": 2,
            "replication_factor": 1,
        })
        assert "error" not in result, result

    @pytest.mark.asyncio
    async def test_create_with_computed_values(self, arango_version):
        major, minor = [int(x) for x in arango_version.split(".")[:2]]
        if major < 3 or (major == 3 and minor < 10):
            pytest.skip("Computed values require ArangoDB 3.10+")
        result = await self.agent.arun({
            "operation": "create_collection",
            "collection_name": "computed_col",
            "computed_values": [{
                "name": "createdAt",
                "expression": "RETURN DATE_ISO8601(DATE_NOW())",
                "overwrite": False,
                "computeOn": ["insert"],
            }],
        })
        assert "error" not in result, result


# ── Index Agent ───────────────────────────────────────────────────────

class TestIndexAgent:
    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector, test_collection):
        self.agent = IndexManagementAgent()
        self.col = test_collection

    @pytest.mark.asyncio
    async def test_list_indexes(self):
        result = await self.agent.arun({
            "operation": "list_indexes",
            "collection_name": self.col,
        })
        assert "indexes" in result
        types = [i["type"] for i in result["indexes"]]
        assert "primary" in types

    @pytest.mark.asyncio
    async def test_create_persistent_index(self):
        result = await self.agent.arun({
            "operation": "create_index",
            "collection_name": self.col,
            "index_definition": {
                "type": "persistent",
                "fields": ["email"],
                "unique": True,
                "name": "test_email_idx",
            },
        })
        assert "error" not in result
        assert result["index_info"]["type"] == "persistent"

    @pytest.mark.asyncio
    async def test_create_inverted_index(self, arango_version):
        major, minor = [int(x) for x in arango_version.split(".")[:2]]
        if major < 3 or (major == 3 and minor < 10):
            pytest.skip("Inverted indexes require ArangoDB 3.10+")
        result = await self.agent.arun({
            "operation": "create_index",
            "collection_name": self.col,
            "index_definition": {
                "type": "inverted",
                "fields": ["description"],
                "name": "test_inv_idx",
            },
        })
        assert "error" not in result
        assert result["index_info"]["type"] == "inverted"

    @pytest.mark.asyncio
    async def test_delete_index(self):
        await self.agent.arun({
            "operation": "create_index",
            "collection_name": self.col,
            "index_definition": {
                "type": "persistent",
                "fields": ["to_delete"],
                "name": "del_idx",
            },
        })
        result = await self.agent.arun({
            "operation": "delete_index",
            "collection_name": self.col,
            "index_id_or_name": "del_idx",
        })
        assert "deleted" in result.get("status", "").lower()

    @pytest.mark.asyncio
    async def test_unsupported_index_type(self):
        result = await self.agent.arun({
            "operation": "create_index",
            "collection_name": self.col,
            "index_definition": {"type": "bogus", "fields": ["x"]},
        })
        assert "error" in result


# ── AQL Agent ─────────────────────────────────────────────────────────

class TestAQLAgent:
    @pytest.fixture(autouse=True)
    def _setup(self, patch_connector, test_collection):
        self.agent = AQLExecutionAgent()
        self.col = test_collection

    @pytest.mark.asyncio
    async def test_simple_return(self):
        result = await self.agent.arun({"aql_query": "RETURN 1"})
        assert "error" not in result
        assert result["results"] == [1]

    @pytest.mark.asyncio
    async def test_query_with_bind_vars(self):
        result = await self.agent.arun({
            "aql_query": "FOR i IN 1..@n RETURN i",
            "bind_vars": {"n": 3},
        })
        assert result["results"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_query_collection(self, test_db, test_collection):
        col = test_db.collection(test_collection)
        col.insert_many([{"v": i} for i in range(5)])
        result = await self.agent.arun({
            "aql_query": f"FOR d IN {test_collection} SORT d.v RETURN d.v",
        })
        assert result["results"] == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_bad_query_returns_error(self):
        result = await self.agent.arun({"aql_query": "THIS IS NOT AQL"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self):
        result = await self.agent.arun({"aql_query": ""})
        assert "error" in result
