"""Embedding tools.

Turns text into vector embeddings so the shared-memory system (and any caller)
can populate a vector index and run semantic / hybrid search.

Provider: OpenAI embeddings REST API (uses httpx, already a dependency — no
openai SDK needed). Configured via environment variables:
  OPENAI_API_KEY   (required)   — API key
  EMBEDDING_MODEL  (optional)   — default "text-embedding-3-small" (1536 dims)

IMPORTANT — do not round-trip raw vectors through an agent. A 1536-float
embedding is ~10-30k tokens. `embed-text` returns vectors for programmatic
callers; agents should instead use `embed-document` (store server-side by key)
and `pattern-search` (embed the query server-side), which keep vectors out of
the agent's context.
"""

import asyncio
import os
from typing import List

import httpx
from pydantic import Field

from arango_connector import arango_connector
from server import mcp_app

_OPENAI_URL = "https://api.openai.com/v1/embeddings"
_DEFAULT_MODEL = "text-embedding-3-small"
_MAX_ATTEMPTS = 3  # retry transient network / 429 / 5xx errors


async def generate_embeddings(texts: List[str], model: str = ""):
    """Embed `texts` via OpenAI. Returns (embeddings, model, dimension). Raises on error.

    Retries up to _MAX_ATTEMPTS on transient failures (network/DNS blips, 429, 5xx)
    with exponential backoff. 4xx (other than 429) fail fast — retrying won't help.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in the server environment. "
                           "Add it to the MCP server env and restart.")
    if not texts:
        raise RuntimeError("No texts provided.")
    chosen = model or os.environ.get("EMBEDDING_MODEL") or _DEFAULT_MODEL

    last_err = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    _OPENAI_URL,
                    headers={"Authorization": f"Bearer {api_key}",
                             "Content-Type": "application/json"},
                    json={"model": chosen, "input": texts},
                )
            if resp.status_code == 200:
                items = sorted(resp.json().get("data", []), key=lambda d: d.get("index", 0))
                embeddings = [item["embedding"] for item in items]
                return embeddings, chosen, (len(embeddings[0]) if embeddings else 0)
            # 429 / 5xx are transient; other 4xx are not
            if resp.status_code != 429 and resp.status_code < 500:
                raise RuntimeError(f"embedding API returned {resp.status_code}: {resp.text[:300]}")
            last_err = RuntimeError(f"embedding API returned {resp.status_code}: {resp.text[:200]}")
        except httpx.HTTPError as exc:  # network/DNS/timeout — transient
            last_err = RuntimeError(f"embedding request failed: {exc}")
        if attempt < _MAX_ATTEMPTS - 1:
            await asyncio.sleep(0.5 * (2 ** attempt))  # 0.5s, 1s
    raise last_err


@mcp_app.tool(
    name="embed-text",
    description="""Generate vector embeddings for one or more text strings.

    Uses OpenAI's embeddings API (model via EMBEDDING_MODEL env, default
    text-embedding-3-small = 1536 dims). Requires OPENAI_API_KEY.

    WARNING: the returned vectors are large (~1536 floats each). For agent
    workflows prefer 'embed-document' (store a doc's embedding server-side) and
    'pattern-search' (embed a query server-side) so vectors never enter the
    agent's context. Use this tool only for programmatic callers that need the
    raw vector.
    """,
)
async def embed_text(
    texts: List[str] = Field(description="Text strings to embed; output order matches input."),
    model: str = Field(default="", description="Optional model override (default EMBEDDING_MODEL "
                                               "env, or text-embedding-3-small)."),
):
    try:
        embeddings, chosen, dim = await generate_embeddings(texts, model)
    except Exception as exc:  # noqa: BLE001
        return {"result": {"error": str(exc)}}
    return {"result": {"model": chosen, "dimension": dim, "count": len(embeddings),
                       "embeddings": embeddings}}


@mcp_app.tool(
    name="embed-document",
    description="""Embed a document's text and store the vector on the document — all
    server-side, so the (large) vector never passes through the caller's context.

    Reads `document_key` from `collection_name`, concatenates `source_fields`
    with newlines, embeds the result, and writes it to `target_field`. Returns
    only {ok, key, model, dimension}. Requires OPENAI_API_KEY.

    Typical use: after saving a shared_patterns doc, call this with the doc's
    _key to populate its `embedding` field for hybrid search.
    """,
)
async def embed_document(
    collection_name: str = Field(description="Collection containing the document."),
    document_key: str = Field(description="_key of the document to embed."),
    source_fields: List[str] = Field(
        default=["problem_description", "solution_summary"],
        description="Fields whose text is concatenated (newline-joined) and embedded."),
    target_field: str = Field(default="embedding",
                              description="Field to store the embedding vector in."),
    database_name: str = Field(default="", description="Target database (default: server default)."),
    model: str = Field(default="", description="Optional embedding model override."),
):
    try:
        db = arango_connector.get_db(database_name or None)
        coll = db.collection(collection_name)
        doc = coll.get(document_key)
        if not doc:
            return {"result": {"error": f"document {document_key!r} not found in "
                                        f"{collection_name!r}"}}
        text = "\n".join(str(doc[f]) for f in source_fields if doc.get(f))
        if not text.strip():
            return {"result": {"error": "no source text to embed in the given fields"}}
        embeddings, chosen, dim = await generate_embeddings([text], model)
        coll.update({"_key": document_key, target_field: embeddings[0]})
        return {"result": {"ok": True, "key": document_key, "model": chosen, "dimension": dim}}
    except Exception as exc:  # noqa: BLE001
        return {"result": {"error": str(exc)}}
