"""Cluster-specific tests — only run against a cluster deployment.

Usage:
    ARANGO_HOSTS=http://localhost:8529 \
      pytest tests/test_cluster.py -m cluster

These tests require a real multi-server deployment. The nightly CI workflow
provisions a pinned three-machine local cluster with ArangoDB Starter.
"""

import pytest
from arango.database import StandardDatabase

pytestmark = pytest.mark.cluster


class TestClusterHealth:
    def test_cluster_detected(self, system_db: StandardDatabase):
        """Verify we're talking to a coordinator, not a single server."""
        role = system_db.cluster.server_role()
        assert role == "COORDINATOR", f"Expected coordinator, got: {role}"

    def test_server_count(self, system_db: StandardDatabase):
        """Cluster should have at least 2 DB servers."""
        health = system_db.cluster.health()
        db_servers = [v for v in health.get("Health", {}).values() if v.get("Role") == "DBServer"]
        assert len(db_servers) >= 2, f"Expected >=2 DB servers, got {len(db_servers)}"


class TestShardedCollection:
    def test_create_sharded_collection(self, test_db: StandardDatabase):
        col = test_db.create_collection(
            "sharded_test",
            shard_count=4,
            shard_fields=["region"],
            replication_factor=2,
        )
        props = col.properties()
        assert props["shard_count"] == 4
        assert props["shard_fields"] == ["region"]
        assert props["replication_factor"] == 2

    def test_shard_distribution(self, test_db: StandardDatabase):
        test_db.create_collection("dist_test", shard_count=3)
        col = test_db.collection("dist_test")
        col.insert_many([{"i": i} for i in range(100)])
        # Verify we can read shard info (collection has shards across servers)
        props = col.properties()
        assert props["shard_count"] == 3

    def test_satellite_collection_flag(self, test_db: StandardDatabase):
        """SatelliteCollections replicate to all DB servers (Enterprise only)."""
        try:
            col = test_db.create_collection(
                "satellite_test",
                replication_factor="satellite",
            )
            props = col.properties()
            assert props["replication_factor"] == "satellite"
        except Exception as e:
            if "enterprise" in str(e).lower() or "license" in str(e).lower():
                pytest.skip("SatelliteCollections require Enterprise Edition")
            raise
