"""Tests for stream transactions and hot backup operations."""

import pytest
from arango.database import StandardDatabase

from agents.backup_management_agent import BackupManagementAgent
from agents.transaction_management_agent import TransactionManagementAgent

# ══════════════════════════════════════════════════════════════════════
#  Stream Transactions
# ══════════════════════════════════════════════════════════════════════


class TestStreamTransactions:
    """Stream transaction lifecycle tests using the TransactionManagementAgent."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: StandardDatabase, test_collection: str, patch_connector):
        self.db = test_db
        self.col_name = test_collection
        self.agent = TransactionManagementAgent()

    # ── Begin / Status / Commit ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_begin_and_commit(self):
        result = await self.agent.arun(
            {
                "operation": "begin_transaction",
                "write": [self.col_name],
            }
        )
        assert "error" not in result
        txn_id = result["transaction_id"]
        assert txn_id

        status = await self.agent.arun(
            {
                "operation": "transaction_status",
                "transaction_id": txn_id,
            }
        )
        assert status["status"] == "running"

        commit = await self.agent.arun(
            {
                "operation": "commit_transaction",
                "transaction_id": txn_id,
            }
        )
        assert "committed" in commit["status"].lower()

    @pytest.mark.asyncio
    async def test_begin_and_abort(self):
        result = await self.agent.arun(
            {
                "operation": "begin_transaction",
                "write": [self.col_name],
            }
        )
        txn_id = result["transaction_id"]

        abort = await self.agent.arun(
            {
                "operation": "abort_transaction",
                "transaction_id": txn_id,
            }
        )
        assert "aborted" in abort["status"].lower()

    # ── Writes are atomic ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_transaction_commit_makes_data_visible(self):
        """Data written inside a committed transaction should be visible."""
        txn_db = self.db.begin_transaction(write=[self.col_name])
        col = txn_db.collection(self.col_name)
        col.insert({"_key": "txn_visible", "value": 42})
        txn_db.commit_transaction()

        doc = self.db.collection(self.col_name).get("txn_visible")
        assert doc is not None
        assert doc["value"] == 42

    @pytest.mark.asyncio
    async def test_transaction_abort_discards_data(self):
        """Data written inside an aborted transaction should not be visible."""
        txn_db = self.db.begin_transaction(write=[self.col_name])
        col = txn_db.collection(self.col_name)
        col.insert({"_key": "txn_gone", "value": 99})
        txn_db.abort_transaction()

        doc = self.db.collection(self.col_name).get("txn_gone")
        assert doc is None

    # ── With read/exclusive collections ──────────────────────────────

    @pytest.mark.asyncio
    async def test_begin_with_read_and_write(self):
        result = await self.agent.arun(
            {
                "operation": "begin_transaction",
                "read": [self.col_name],
                "write": [self.col_name],
            }
        )
        assert "error" not in result
        txn_id = result["transaction_id"]

        await self.agent.arun({"operation": "abort_transaction", "transaction_id": txn_id})

    @pytest.mark.asyncio
    async def test_begin_with_exclusive(self):
        result = await self.agent.arun(
            {
                "operation": "begin_transaction",
                "exclusive": [self.col_name],
            }
        )
        assert "error" not in result
        txn_id = result["transaction_id"]

        await self.agent.arun({"operation": "abort_transaction", "transaction_id": txn_id})

    # ── List transactions ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_transactions(self):
        begin = await self.agent.arun(
            {
                "operation": "begin_transaction",
                "write": [self.col_name],
            }
        )
        txn_id = begin["transaction_id"]

        listed = await self.agent.arun({"operation": "list_transactions"})
        assert "error" not in listed
        assert "transactions" in listed

        txn_ids = [t.get("id") for t in listed["transactions"]]
        assert txn_id in txn_ids

        await self.agent.arun({"operation": "abort_transaction", "transaction_id": txn_id})

    # ── Bad transaction ID ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_status_bad_id(self):
        result = await self.agent.arun(
            {
                "operation": "transaction_status",
                "transaction_id": "99999999",
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_commit_bad_id(self):
        result = await self.agent.arun(
            {
                "operation": "commit_transaction",
                "transaction_id": "99999999",
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_abort_bad_id(self):
        result = await self.agent.arun(
            {
                "operation": "abort_transaction",
                "transaction_id": "99999999",
            }
        )
        assert "error" in result

    # ── Missing transaction_id ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_status_missing_id(self):
        result = await self.agent.arun({"operation": "transaction_status"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_commit_missing_id(self):
        result = await self.agent.arun({"operation": "commit_transaction"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_abort_missing_id(self):
        result = await self.agent.arun({"operation": "abort_transaction"})
        assert "error" in result

    # ── Execute JS transaction ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_execute_js_transaction(self):
        self.db.collection(self.col_name).insert({"_key": "seed", "counter": 0})

        result = await self.agent.arun(
            {
                "operation": "execute_transaction",
                "command": """
                    function(params) {
                        var db = require('@arangodb').db;
                        var col = db._collection(params.collection);
                        col.update('seed', { counter: 10 });
                        return col.document('seed').counter;
                    }
                """,
                "params": {"collection": self.col_name},
                "write": [self.col_name],
            }
        )
        assert "error" not in result
        assert result["result"] == 10

    @pytest.mark.asyncio
    async def test_execute_js_transaction_missing_command(self):
        result = await self.agent.arun(
            {
                "operation": "execute_transaction",
                "write": [self.col_name],
            }
        )
        assert "error" in result

    # ── Unknown operation ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_unknown_operation(self):
        result = await self.agent.arun({"operation": "nonexistent"})
        assert "error" in result


# ══════════════════════════════════════════════════════════════════════
#  Hot Backup (Enterprise Edition)
# ══════════════════════════════════════════════════════════════════════


class TestHotBackup:
    """Hot backup tests — expected to gracefully report 'Enterprise only'
    when run against the Community Edition Docker image."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: StandardDatabase, patch_connector):
        self.db = test_db
        self.agent = BackupManagementAgent()

    @pytest.mark.asyncio
    async def test_create_backup_community(self):
        """On Community Edition, create should return an enterprise error."""
        result = await self.agent.arun({"operation": "create_backup"})
        if "error" in result:
            assert "enterprise" in result["error"].lower()
        else:
            assert "backup" in result

    @pytest.mark.asyncio
    async def test_list_backups_community(self):
        result = await self.agent.arun({"operation": "list_backups"})
        if "error" in result:
            assert "enterprise" in result["error"].lower()
        else:
            assert "backups" in result

    @pytest.mark.asyncio
    async def test_delete_backup_community(self):
        result = await self.agent.arun({"operation": "delete_backup", "backup_id": "nonexistent"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_restore_backup_community(self):
        result = await self.agent.arun({"operation": "restore_backup", "backup_id": "nonexistent"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_restore_missing_id(self):
        result = await self.agent.arun({"operation": "restore_backup"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_delete_missing_id(self):
        result = await self.agent.arun({"operation": "delete_backup"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_unknown_operation(self):
        result = await self.agent.arun({"operation": "nonexistent"})
        assert "error" in result
