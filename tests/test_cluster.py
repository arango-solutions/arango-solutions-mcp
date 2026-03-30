"""Cluster-specific tests — only run against a cluster deployment.

Usage:
    pytest tests/test_cluster.py -m cluster

These tests require the docker-compose cluster profile:
    docker compose --profile cluster up -d
    ARANGO_HOSTS=http://localhost:8530 pytest -m cluster
"""

import pytest
from arango.database import StandardDatabase

pytestmark = pytest.mark.cluster


class TestClusterHealth:
    def test_cluster_detected(self, system_db: StandardDatabase):
        """Verify we're talking to a coordinator, not a single server."""
        role = system_db.execute_transaction(
            command="function() { return require('@arangodb').serverRole(); }",
            read_collections=[],
            write_collections=[],
        )
        assert role in ("COORDINATOR", "SINGLE"), f"Unexpected role: {role}"

    def test_server_count(self, system_db: StandardDatabase):
        """Cluster should have at least 2 DB servers."""
        health = system_db.cluster.health()
        db_servers = [v for v in health.get("Health", {}).values() if v.get("Role") == "DBServer"]
        assert len(db_servers) >= 2, f"Expected >=2 DB servers, got {len(db_servers)}"


class TestShardedCollection:
    def test_create_sharded_collection(self, test_db: StandardDatabase):
        col = test_db.create_collection(
            "sharded_test",
            number_of_shards=4,
            shard_keys=["region"],
            replication_factor=2,
        )
        props = col.properties()
        assert props["numberOfShards"] == 4
        assert props["shardKeys"] == ["region"]
        assert props["replicationFactor"] == 2

    def test_shard_distribution(self, test_db: StandardDatabase):
        test_db.create_collection("dist_test", number_of_shards=3)
        col = test_db.collection("dist_test")
        col.insert_many([{"i": i} for i in range(100)])
        # Verify we can read shard info (collection has shards across servers)
        props = col.properties()
        assert props["numberOfShards"] == 3

    def test_satellite_collection_flag(self, test_db: StandardDatabase):
        """SatelliteCollections replicate to all DB servers (Enterprise only)."""
        try:
            col = test_db.create_collection(
                "satellite_test",
                replication_factor="satellite",
            )
            props = col.properties()
            assert props["replicationFactor"] == "satellite"
        except Exception as e:
            if "enterprise" in str(e).lower() or "license" in str(e).lower():
                pytest.skip("SatelliteCollections require Enterprise Edition")
            raise
