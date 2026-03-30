"""Smoke tests: can we reach ArangoDB and do basic operations?"""

import pytest
from arango.database import StandardDatabase


class TestConnectivity:
    def test_server_version(self, arango_version: str):
        assert arango_version, "Server did not return a version string"
        major = int(arango_version.split(".")[0])
        assert major >= 3, f"Expected ArangoDB 3.x+, got {arango_version}"

    def test_system_db_accessible(self, system_db: StandardDatabase):
        props = system_db.properties()
        assert props is not None

    def test_ephemeral_db_created(self, test_db: StandardDatabase, test_db_name: str):
        assert test_db.name == test_db_name


class TestCollectionBasics:
    def test_create_document_collection(self, test_db: StandardDatabase):
        col = test_db.create_collection("smoke_docs")
        assert col.name == "smoke_docs"
        props = col.properties()
        assert props["type"] == 2  # document collection

    def test_create_edge_collection(self, test_db: StandardDatabase):
        col = test_db.create_collection("smoke_edges", edge=True)
        assert col.name == "smoke_edges"
        props = col.properties()
        assert props["type"] == 3  # edge collection


class TestDocumentBasics:
    def test_insert_and_read(self, test_db: StandardDatabase, test_collection: str):
        col = test_db.collection(test_collection)
        meta = col.insert({"name": "alice", "score": 42})
        assert "_key" in meta
        doc = col.get(meta["_key"])
        assert doc["name"] == "alice"
        assert doc["score"] == 42

    def test_update_document(self, test_db: StandardDatabase, test_collection: str):
        col = test_db.collection(test_collection)
        meta = col.insert({"name": "bob", "level": 1})
        col.update({"_key": meta["_key"], "level": 2})
        doc = col.get(meta["_key"])
        assert doc["level"] == 2
        assert doc["name"] == "bob"  # preserved by merge update

    def test_delete_document(self, test_db: StandardDatabase, test_collection: str):
        col = test_db.collection(test_collection)
        meta = col.insert({"temp": True})
        col.delete(meta["_key"])
        assert col.get(meta["_key"]) is None

    def test_replace_document(self, test_db: StandardDatabase, test_collection: str):
        col = test_db.collection(test_collection)
        meta = col.insert({"name": "carol", "old_field": True})
        col.replace({"_key": meta["_key"], "name": "carol_v2"})
        doc = col.get(meta["_key"])
        assert doc["name"] == "carol_v2"
        assert "old_field" not in doc


class TestAQLBasics:
    def test_simple_query(self, test_db: StandardDatabase, test_collection: str):
        col = test_db.collection(test_collection)
        col.insert_many([{"val": i} for i in range(5)])
        cursor = test_db.aql.execute(
            "FOR d IN @@col SORT d.val RETURN d.val",
            bind_vars={"@col": test_collection},
        )
        assert list(cursor) == [0, 1, 2, 3, 4]


class TestIndexBasics:
    def test_persistent_index(self, test_db: StandardDatabase, test_collection: str):
        col = test_db.collection(test_collection)
        idx = col.add_index(
            {"type": "persistent", "fields": ["email"], "unique": True, "name": "idx_email"}
        )
        assert idx["type"] == "persistent"
        indexes = col.indexes()
        names = [i.get("name") for i in indexes]
        assert "idx_email" in names

    def test_inverted_index(
        self, test_db: StandardDatabase, test_collection: str, arango_version: str
    ):
        major, minor = [int(x) for x in arango_version.split(".")[:2]]
        if major < 3 or (major == 3 and minor < 10):
            pytest.skip("Inverted indexes require ArangoDB 3.10+")
        col = test_db.collection(test_collection)
        idx = col.add_index(
            {"type": "inverted", "fields": [{"name": "description"}], "name": "idx_inv_desc"}
        )
        assert idx["type"] == "inverted"
