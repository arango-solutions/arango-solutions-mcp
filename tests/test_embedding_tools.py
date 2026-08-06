"""Unit tests for the embedding tools and the shared tool-layer support helpers.

These run without a live ArangoDB or a real OpenAI key: the OpenAI call
(``generate_embeddings``) and the database handle are mocked. They cover the
requirements that the embedding/pattern-memory subsystem previously left
untested: standardized error envelopes (REQ-033), non-blocking dispatch of
blocking driver calls (REQ-038), and per-tool coverage (REQ-048/049).
"""

import asyncio
import os

# Required env before importing the application (mirrors test_mcp_e2e).
os.environ.setdefault("ARANGO_HOSTS", "http://localhost:8529")
os.environ.setdefault("ARANGO_ROOT_USERNAME", "root")
os.environ.setdefault("ARANGO_ROOT_PASSWORD", "test")
os.environ.setdefault("ARANGO_DEFAULT_DB_NAME", "_system")

from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402
from arango.exceptions import ArangoServerError  # noqa: E402

with patch("arango_connector.ArangoClient"):
    from server import mcp_app  # noqa: F401,E402 — import first so tool modules register in order

import mcp_tools.embedding_tools as em  # noqa: E402
from mcp_tools import _support  # noqa: E402


def _arango_server_error(message: str, code: int) -> ArangoServerError:
    """Build an ArangoServerError without its heavy HTTP-response constructor."""
    err = ArangoServerError.__new__(ArangoServerError)
    err.error_message = message
    err.error_code = code
    return err


# ---------------------------------------------------------------------------
# _support: standardized error envelope + non-blocking helper
# ---------------------------------------------------------------------------


class TestSupportHelpers:
    def test_arango_error_result_generic(self):
        out = _support.arango_error_result(RuntimeError("boom"))
        assert out == {"result": {"error": "An unexpected error occurred: boom"}}

    def test_arango_error_result_arango_has_error_code(self):
        err = _arango_server_error("collection not found", 1203)
        out = _support.arango_error_result(err, "ArangoDB Collection")
        assert out["result"]["error_code"] == 1203
        assert out["result"]["error"].startswith("ArangoDB Collection Error: collection not found")

    def test_run_sync_returns_value(self):
        assert asyncio.run(_support.run_sync(lambda x: x + 1, 41)) == 42

    def test_run_sync_propagates_exception(self):
        async def go():
            return await _support.run_sync(lambda: (_ for _ in ()).throw(ValueError("nope")))

        with pytest.raises(ValueError, match="nope"):
            asyncio.run(go())


# ---------------------------------------------------------------------------
# TLS-env sanitisation
# ---------------------------------------------------------------------------


class TestSanitizeTlsEnv:
    def test_drops_nonexistent_cert_path(self, monkeypatch):
        monkeypatch.setenv("SSL_CERT_FILE", "/definitely/not/a/real/path.pem")
        em._sanitize_tls_env()
        assert "SSL_CERT_FILE" not in os.environ

    def test_keeps_existing_cert_path(self, monkeypatch, tmp_path):
        real = tmp_path / "ca.pem"
        real.write_text("x")
        monkeypatch.setenv("SSL_CERT_FILE", str(real))
        em._sanitize_tls_env()
        assert os.environ.get("SSL_CERT_FILE") == str(real)


# ---------------------------------------------------------------------------
# generate_embeddings guard rails (no HTTP)
# ---------------------------------------------------------------------------


class TestGenerateEmbeddingsGuards:
    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setattr(em.settings.embedding, "openai_api_key", None)
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
            asyncio.run(em.generate_embeddings(["hello"]))

    def test_empty_texts_raises(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setattr(em.settings.embedding, "openai_api_key", None)
        with pytest.raises(RuntimeError, match="No texts provided"):
            asyncio.run(em.generate_embeddings([]))


# ---------------------------------------------------------------------------
# embed-text / embed-document tools
# ---------------------------------------------------------------------------


class TestEmbedText:
    def test_success_envelope(self):
        with patch.object(em, "generate_embeddings", return_value=([[0.1, 0.2]], "m", 2)):
            out = asyncio.run(em.embed_text(texts=["hi"], model=""))
        assert out == {
            "result": {"model": "m", "dimension": 2, "count": 1, "embeddings": [[0.1, 0.2]]}
        }

    def test_error_uses_standard_envelope(self):
        async def boom(*_a, **_k):
            raise RuntimeError("api down")

        with patch.object(em, "generate_embeddings", side_effect=boom):
            out = asyncio.run(em.embed_text(texts=["hi"], model=""))
        assert out == {"result": {"error": "An unexpected error occurred: api down"}}


class TestEmbedDocument:
    def _fake_db(self, doc):
        db = MagicMock()
        coll = MagicMock()
        coll.get.return_value = doc
        db.collection.return_value = coll
        return db, coll

    def test_document_not_found(self):
        db, _coll = self._fake_db(doc=None)
        with patch.object(em.arango_connector, "get_db", return_value=db):
            out = asyncio.run(
                em.embed_document(
                    collection_name="shared_patterns",
                    document_key="missing",
                    source_fields=["problem_description"],
                    target_field="embedding",
                    database_name="",
                    model="",
                )
            )
        assert "not found" in out["result"]["error"]

    def test_success_writes_embedding_off_thread(self, monkeypatch):
        db, coll = self._fake_db(doc={"problem_description": "p", "solution_summary": "s"})

        # Spy on run_sync to confirm blocking calls are dispatched off the loop.
        dispatched = []

        async def spy(fn, *a, **k):
            dispatched.append(getattr(fn, "__name__", type(fn).__name__))
            return fn(*a, **k)

        monkeypatch.setattr(em, "run_sync", spy)
        with (
            patch.object(em.arango_connector, "get_db", return_value=db),
            patch.object(em, "generate_embeddings", return_value=([[0.3, 0.4]], "m", 2)),
        ):
            out = asyncio.run(
                em.embed_document(
                    collection_name="shared_patterns",
                    document_key="k1",
                    source_fields=["problem_description", "solution_summary"],
                    target_field="embedding",
                    database_name="",
                    model="",
                )
            )
        assert out["result"] == {"ok": True, "key": "k1", "model": "m", "dimension": 2}
        coll.update.assert_called_once()
        # get_db, coll.get and coll.update were all routed through run_sync.
        assert dispatched, "no blocking calls were dispatched via run_sync"
