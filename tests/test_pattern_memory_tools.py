"""Unit tests for the shared-memory pattern tools.

Mock-based (no live ArangoDB, no OpenAI key). They lock in the behaviours the
refactor added to close drift: blocking driver calls are dispatched via
``run_sync`` off the event loop (REQ-038), every failure returns the standard
``{"result": {"error", "error_code"}}`` envelope (REQ-033), and each of the five
tools has direct coverage (REQ-048/049).
"""

import asyncio
import os

os.environ.setdefault("ARANGO_HOSTS", "http://localhost:8529")
os.environ.setdefault("ARANGO_ROOT_USERNAME", "root")
os.environ.setdefault("ARANGO_ROOT_PASSWORD", "test")
os.environ.setdefault("ARANGO_DEFAULT_DB_NAME", "_system")

from unittest.mock import MagicMock, patch  # noqa: E402

from arango.exceptions import ArangoServerError  # noqa: E402

with patch("arango_connector.ArangoClient"):
    from server import mcp_app  # noqa: F401,E402 — import first so tool modules register in order

import mcp_tools.pattern_memory_tools as pm  # noqa: E402


def _arango_server_error(message: str, code: int) -> ArangoServerError:
    err = ArangoServerError.__new__(ArangoServerError)
    err.error_message = message
    err.error_code = code
    return err


def _dispatch_spy():
    """A run_sync replacement that records the callables it dispatches and runs
    them inline (synchronously) so tests stay deterministic."""
    dispatched = []

    async def spy(fn, *args, **kwargs):
        dispatched.append(getattr(fn, "__name__", type(fn).__name__))
        return fn(*args, **kwargs)

    spy.dispatched = dispatched
    return spy


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_ekey_sanitizes(self):
        key = pm._ekey("patterns/a b", "c/d")
        assert " " not in key and "/" not in key
        assert key == "patterns-a-b__c-d"

    def test_has_vector_index_true(self):
        coll = MagicMock()
        coll.indexes.return_value = [{"type": "persistent"}, {"type": "vector"}]
        assert pm._has_vector_index(coll) is True

    def test_has_vector_index_false(self):
        coll = MagicMock()
        coll.indexes.return_value = [{"type": "persistent"}]
        assert pm._has_vector_index(coll) is False

    def test_vector_dim_reads_index_params(self):
        coll = MagicMock()
        coll.indexes.return_value = [{"type": "vector", "params": {"dimension": 768}}]
        assert pm._vector_dim(coll) == 768

    def test_vector_dim_default_when_absent(self):
        coll = MagicMock()
        coll.indexes.return_value = []
        assert pm._vector_dim(coll, default=1536) == 1536


# ---------------------------------------------------------------------------
# pattern-search (BM25 fallback path — no vector index, no embeddings)
# ---------------------------------------------------------------------------


class TestPatternSearch:
    def test_bm25_fallback_returns_patterns_and_dispatches_off_thread(self, monkeypatch):
        db = MagicMock()
        coll = MagicMock()
        coll.indexes.return_value = []          # no vector index -> BM25 mode
        db.collection.return_value = coll
        db.has_collection.return_value = True
        db.aql.execute.return_value = [{"_key": "p1", "relevance": 0.9}]

        spy = _dispatch_spy()
        monkeypatch.setattr(pm, "run_sync", spy)
        with patch.object(pm.arango_connector, "get_db", return_value=db):
            out = asyncio.run(pm.pattern_search(
                query_text="anything", limit=8, graph_expand=True,
                collection_name="shared_patterns", view_name="patterns_search",
                database_name="", model="", project_id="arango-solutions-mcp-server"))

        assert out["result"]["mode"] == "bm25"
        assert out["result"]["count"] == 1
        assert out["result"]["patterns"] == [{"_key": "p1", "relevance": 0.9}]
        # the blocking DB work was routed off the event loop via run_sync
        assert "_run_query" in spy.dispatched
        assert "_log_search" in spy.dispatched

    def test_error_uses_standard_envelope(self, monkeypatch):
        spy = _dispatch_spy()
        monkeypatch.setattr(pm, "run_sync", spy)
        err = _arango_server_error("view missing", 1203)
        with patch.object(pm.arango_connector, "get_db", side_effect=err):
            out = asyncio.run(pm.pattern_search(
                query_text="x", limit=8, graph_expand=True,
                collection_name="shared_patterns", view_name="patterns_search",
                database_name="", model="", project_id=""))
        assert out["result"]["error_code"] == 1203


# ---------------------------------------------------------------------------
# pattern-applied
# ---------------------------------------------------------------------------


class TestPatternApplied:
    def test_empty_keys_short_circuits(self):
        out = asyncio.run(pm.pattern_applied(keys=[], collection_name="shared_patterns",
                                             database_name=""))
        assert out == {"result": {"error": "no keys provided"}}

    def test_bumps_usage_and_reports_missing(self, monkeypatch):
        db = MagicMock()
        db.aql.execute.return_value = [{"_key": "k1", "usage_count": 3, "applied_worked": 3,
                                        "applied_failed": 0}]
        spy = _dispatch_spy()
        monkeypatch.setattr(pm, "run_sync", spy)
        with patch.object(pm.arango_connector, "get_db", return_value=db):
            out = asyncio.run(pm.pattern_applied(keys=["k1", "gone"], outcome="worked",
                                                 collection_name="shared_patterns",
                                                 database_name=""))
        assert out["result"]["count"] == 1
        assert out["result"]["outcome"] == "worked"
        assert out["result"]["not_found"] == ["gone"]
        assert "_run_query" in spy.dispatched

    def test_failed_outcome_records_negative_signal(self, monkeypatch):
        db = MagicMock()
        db.aql.execute.return_value = [{"_key": "k1", "usage_count": 2, "applied_worked": 2,
                                        "applied_failed": 1}]
        spy = _dispatch_spy()
        monkeypatch.setattr(pm, "run_sync", spy)
        captured = {}
        real = pm._run_query

        def _cap(db_, aql, binds):
            captured["aql"] = aql
            captured["binds"] = binds
            return real(db_, aql, binds)

        monkeypatch.setattr(pm, "_run_query", _cap)
        with patch.object(pm.arango_connector, "get_db", return_value=db):
            out = asyncio.run(pm.pattern_applied(keys=["k1"], outcome="failed",
                                                 collection_name="shared_patterns",
                                                 database_name=""))
        assert out["result"]["outcome"] == "failed"
        # a failed apply must NOT reward usage/recency, and must record negative signal
        assert captured["binds"]["worked"] is False
        assert "applied_failed: @worked ? af : af + 1" in captured["aql"]


# ---------------------------------------------------------------------------
# save-drift-alert
# ---------------------------------------------------------------------------


class TestSaveDriftAlert:
    def test_missing_collection_error(self, monkeypatch):
        db = MagicMock()
        db.has_collection.return_value = False
        spy = _dispatch_spy()
        monkeypatch.setattr(pm, "run_sync", spy)
        with patch.object(pm.arango_connector, "get_db", return_value=db):
            out = asyncio.run(pm.save_drift_alert(
                project_id="p", req_id="REQ-001", requirement="r", classification="MISSING",
                status="open", evidence="", gap_description="g", detected_at="",
                closed_at="", closed_evidence="", collection_name="drift_alerts",
                database_name=""))
        assert "not found" in out["result"]["error"]

    def test_success_upserts_and_links_provenance(self, monkeypatch):
        db = MagicMock()
        db.has_collection.return_value = True
        db.aql.execute.return_value = []
        spy = _dispatch_spy()
        monkeypatch.setattr(pm, "run_sync", spy)
        with patch.object(pm.arango_connector, "get_db", return_value=db):
            out = asyncio.run(pm.save_drift_alert(
                project_id="proj", req_id="REQ-007", requirement="r", classification="PARTIAL",
                status="open", evidence="f.py:1", gap_description="g", detected_at="2026-01-01T00:00:00Z",
                closed_at="", closed_evidence="", collection_name="drift_alerts",
                database_name=""))
        assert out["result"]["_key"] == "proj_REQ-007"
        assert out["result"]["status"] == "open"
        assert "_ensure_provenance" in spy.dispatched


# ---------------------------------------------------------------------------
# save-pattern (embedding supplied, no vector index -> no graph edges)
# ---------------------------------------------------------------------------


class TestSavePattern:
    def test_insert_and_provenance(self, monkeypatch):
        db = MagicMock()
        # Distinct collection mock per name so the pattern insert and the
        # provenance-edge insert don't collide on one shared mock.
        colls: dict = {}
        db.collection.side_effect = lambda name: colls.setdefault(name, MagicMock())
        coll = db.collection("shared_patterns")
        coll.indexes.return_value = []           # no vector index
        db.has_collection.return_value = True
        db.aql.execute.return_value = []
        spy = _dispatch_spy()
        monkeypatch.setattr(pm, "run_sync", spy)
        with patch.object(pm.arango_connector, "get_db", return_value=db), \
                patch.object(pm, "generate_embeddings", return_value=([[0.1, 0.2, 0.3]], "m", 3)):
            out = asyncio.run(pm.save_pattern(
                problem_description="p", solution_summary="s", problem_category="testing",
                project_id="arango-solutions-mcp-server", project_type="mcp-server", tags=["t"],
                importance=7, source_file="", worked=True, created_at="",
                collection_name="shared_patterns", database_name="", model="",
                rel_sim=0.3, sup_sim=0.9, top_k=3))
        res = out["result"]
        assert res["embedded"] is True
        assert res["embedding_pending"] is False
        assert res["relates_edges"] == 0
        coll.insert.assert_called_once()
        assert "coll" not in res  # sanity: no raw handles leak into the response
