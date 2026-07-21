"""Shared-memory pattern search.

Server-side hybrid retrieval for the shared_patterns collection so agents pass a
query string and receive only ranked results — the (large) query embedding is
generated and consumed inside the server, never in the agent's context.

Ranking: Reciprocal Rank Fusion (k=60) of ANN vector similarity and BM25
full-text, normalized and combined with graded salience (importance, recency
exponential decay, usage). Falls back to BM25-only if embeddings are
unavailable or the collection has no vector index.
"""

import datetime
import re
from typing import List

from pydantic import Field

from arango_connector import arango_connector
from mcp_tools.embedding_tools import generate_embeddings
from server import mcp_app


def _ekey(a: str, b: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "-", f"{a}__{b}")[:250]


def _ensure_provenance(db, edge_coll, src_id, project_id, relation):
    """Upsert the project_registry node and insert a provenance edge
    (src_id -> project_registry/<project_id>).

    Used on the write path so every pattern / drift alert is linked to its
    project and no project becomes an orphan node. No-op if project_id is empty
    or the edge collection is absent (keyword-only / graph layer not set up).
    Idempotent: deterministic edge _key + overwrite=True.
    """
    if not project_id or not db.has_collection(edge_coll):
        return False
    if db.has_collection("project_registry"):
        db.aql.execute(
            "UPSERT { _key: @pid } "
            "INSERT { _key: @pid, project_id: @pid, project_name: @pid, "
            "project_type: 'other', open_gaps: 0, patterns_contributed: 0, "
            "last_sync: null, autocreated: true } UPDATE { } IN project_registry",
            bind_vars={"pid": project_id})
    src_key = src_id.split("/", 1)[-1]
    db.collection(edge_coll).insert(
        {"_key": _ekey(src_key, project_id), "_from": src_id,
         "_to": f"project_registry/{project_id}", "relation": relation}, overwrite=True)
    return True


# KNN over stored embeddings: APPROX_NEAR_COSINE must be bound via LET + used once in SORT.
_KNN_AQL = ("FOR q IN @@coll LET s = APPROX_NEAR_COSINE(q.embedding, @vec) "
            "SORT s DESC LIMIT @lim RETURN {k: q._key, s: s, created: q.created_at}")


def _maintain_graph(db, coll, coll_name, key, embedding, created_at, rel_sim, sup_sim, top_k,
                    project_id=None):
    """Maintain graph edges for one just-saved pattern. Sync.

    ALWAYS records provenance (pattern_from_project: pattern -> project_registry),
    independent of embeddings, auto-creating the project node if the project never
    ran /prd-sync -- so every saved pattern is linked to its project and neither
    the pattern nor the project becomes an orphan in the graph. Then, when an
    embedding + vector index exist, builds pattern_relates_to (KNN) edges and a
    supersede check.

    Returns (relates_edges:int, superseded:dict|None).
    """
    # --- provenance: pattern -> project (no embedding needed). Historically this
    # lived only in phase2_setup.py, so patterns saved via the tool never got a
    # provenance edge and their projects showed up as orphan nodes. ---
    _ensure_provenance(db, "pattern_from_project", f"{coll_name}/{key}",
                       project_id or (coll.get(key) or {}).get("project_id"), "from_project")

    if not embedding or not _has_vector_index(coll):
        return 0, None
    k = max(1, min(int(top_k), 10))
    nbrs = [n for n in db.aql.execute(_KNN_AQL, bind_vars={
        "vec": embedding, "lim": k + 1, "@coll": coll_name}) if n["k"] != key]

    rel_edges = 0
    if db.has_collection("pattern_relates_to"):
        rc = db.collection("pattern_relates_to")
        for n in nbrs:
            if n["s"] >= rel_sim:
                rc.insert({"_key": _ekey(key, n["k"]),
                           "_from": f"{coll_name}/{key}", "_to": f"{coll_name}/{n['k']}",
                           "sim": round(n["s"], 4)}, overwrite=True)
                rel_edges += 1

    superseded = None
    top = nbrs[0] if nbrs else None
    if top and top["s"] >= sup_sim and db.has_collection("pattern_supersedes"):
        new_k, old_k = ((key, top["k"]) if (created_at or "") >= (top["created"] or "")
                        else (top["k"], key))
        db.collection("pattern_supersedes").insert({
            "_key": _ekey(new_k, old_k), "_from": f"{coll_name}/{new_k}",
            "_to": f"{coll_name}/{old_k}", "sim": round(top["s"], 4)}, overwrite=True)
        old = coll.get(old_k)
        coll.update({"_key": old_k, "superseded": True, "superseded_by": new_k,
                     "importance_original": old.get("importance_original", old.get("importance", 5)),
                     "importance": 1})
        superseded = {"new": new_k, "old": old_k, "sim": round(top["s"], 4)}
    return rel_edges, superseded

# Hybrid: vector ⊕ BM25 via RRF, then graded scoring.
_HYBRID_AQL = """
LET vec = (FOR p IN @@coll
             SORT APPROX_NEAR_COSINE(p.embedding, @qvec) DESC LIMIT 25 RETURN p._key)
LET bm  = (FOR p IN @@view
             SEARCH ANALYZER(
               p.problem_description IN TOKENS(@q,"text_en")
               OR p.solution_summary IN TOKENS(@q,"text_en")
               OR p.tags            IN TOKENS(@q,"text_en"), "text_en")
             SORT BM25(p) DESC LIMIT 25 RETURN p._key)
LET fused = (FOR k IN UNIQUE(APPEND(vec, bm))
  LET vr = POSITION(vec, k, true)
  LET br = POSITION(bm,  k, true)
  RETURN { k, rrf: (vr == -1 ? 0 : 1.0/(60+vr+1)) + (br == -1 ? 0 : 1.0/(60+br+1)) })
LET maxRrf = MAX(fused[*].rrf)
FOR f IN fused
  LET p = DOCUMENT(@@coll, f.k)
  FILTER p.superseded != true
  LET rel = f.rrf / (maxRrf > 0 ? maxRrf : 1)
  LET imp = (p.importance == null ? 5 : p.importance) / 10.0
  LET rec = POW(0.995, DATE_DIFF(p.last_used == null ? p.created_at : p.last_used, DATE_NOW(), "d"))
  LET use = LOG(1 + (p.usage_count == null ? 0 : p.usage_count)) / LOG(11)
  LET score = rel + imp + rec + use
  SORT score DESC LIMIT @lim
  RETURN { _key: p._key, project_id: p.project_id, project_type: p.project_type,
           problem_category: p.problem_category, problem_description: p.problem_description,
           solution_summary: p.solution_summary, tags: p.tags, created_at: p.created_at,
           source_file: p.source_file, importance: p.importance, usage_count: p.usage_count,
           score: ROUND(score*1000)/1000, relevance: ROUND(rel*1000)/1000 }
"""

# Hybrid + graph expansion: adds 1-hop pattern_relates_to neighbors of the top vector
# seeds into the candidate pool (Phase 2). Graph-only nodes get a small RRF floor so they
# surface for scoring but rank below direct vector/BM25 hits.
_HYBRID_GRAPH_AQL = """
LET vec = (FOR p IN @@coll
             SORT APPROX_NEAR_COSINE(p.embedding, @qvec) DESC LIMIT 25 RETURN p._key)
LET bm  = (FOR p IN @@view
             SEARCH ANALYZER(
               p.problem_description IN TOKENS(@q,"text_en")
               OR p.solution_summary IN TOKENS(@q,"text_en")
               OR p.tags            IN TOKENS(@q,"text_en"), "text_en")
             SORT BM25(p) DESC LIMIT 25 RETURN p._key)
LET seeds = SLICE(vec, 0, 5)
LET nbrs = UNIQUE(FLATTEN(
  FOR s IN seeds
    RETURN (FOR n IN 1..1 ANY DOCUMENT(@@coll, s) pattern_relates_to RETURN n._key)))
LET fused = (FOR k IN UNIQUE(APPEND(APPEND(vec, bm), nbrs))
  LET vr = POSITION(vec, k, true)
  LET br = POSITION(bm,  k, true)
  LET graphOnly = (vr == -1 AND br == -1 AND POSITION(nbrs, k, true) != -1)
  RETURN { k, rrf: (vr == -1 ? 0 : 1.0/(60+vr+1)) + (br == -1 ? 0 : 1.0/(60+br+1))
                   + (graphOnly ? 1.0/(60+30) : 0), graphOnly })
LET maxRrf = MAX(fused[*].rrf)
FOR f IN fused
  LET p = DOCUMENT(@@coll, f.k)
  FILTER p.superseded != true
  LET rel = f.rrf / (maxRrf > 0 ? maxRrf : 1)
  LET imp = (p.importance == null ? 5 : p.importance) / 10.0
  LET rec = POW(0.995, DATE_DIFF(p.last_used == null ? p.created_at : p.last_used, DATE_NOW(), "d"))
  LET use = LOG(1 + (p.usage_count == null ? 0 : p.usage_count)) / LOG(11)
  LET score = rel + imp + rec + use
  SORT score DESC LIMIT @lim
  RETURN { _key: p._key, project_id: p.project_id, project_type: p.project_type,
           problem_category: p.problem_category, problem_description: p.problem_description,
           solution_summary: p.solution_summary, tags: p.tags, created_at: p.created_at,
           source_file: p.source_file, importance: p.importance, usage_count: p.usage_count,
           via_graph: f.graphOnly, score: ROUND(score*1000)/1000, relevance: ROUND(rel*1000)/1000 }
"""

# BM25-only fallback (no query vector).
_BM25_AQL = """
LET cand = (FOR p IN @@view
  SEARCH ANALYZER(
    p.problem_description IN TOKENS(@q,"text_en")
    OR p.solution_summary IN TOKENS(@q,"text_en")
    OR p.tags            IN TOKENS(@q,"text_en"), "text_en")
  LET rel = BM25(p) SORT rel DESC LIMIT 25 RETURN { p, rel })
LET maxRel = MAX(cand[*].rel)
FOR c IN cand
  FILTER c.p.superseded != true
  LET rel = c.rel / (maxRel > 0 ? maxRel : 1)
  LET imp = (c.p.importance == null ? 5 : c.p.importance) / 10.0
  LET rec = POW(0.995, DATE_DIFF(c.p.last_used == null ? c.p.created_at : c.p.last_used, DATE_NOW(), "d"))
  LET use = LOG(1 + (c.p.usage_count == null ? 0 : c.p.usage_count)) / LOG(11)
  LET score = rel + imp + rec + use
  SORT score DESC LIMIT @lim
  RETURN { _key: c.p._key, project_id: c.p.project_id, project_type: c.p.project_type,
           problem_category: c.p.problem_category, problem_description: c.p.problem_description,
           solution_summary: c.p.solution_summary, tags: c.p.tags, created_at: c.p.created_at,
           source_file: c.p.source_file, importance: c.p.importance, usage_count: c.p.usage_count,
           score: ROUND(score*1000)/1000, relevance: ROUND(rel*1000)/1000 }
"""


def _has_vector_index(coll) -> bool:
    return any(ix.get("type") == "vector" for ix in coll.indexes())


def _vector_dim(coll, default: int = 1536) -> int:
    """Dimension of the collection's vector index (for placeholder vectors)."""
    for ix in coll.indexes():
        if ix.get("type") == "vector":
            return int(ix.get("params", {}).get("dimension", default))
    return default


# A search is a "hit" when its top result clears this normalized-relevance bar.
# (relevance is RRF- or BM25-normalized to ~[0,1] in the search AQL.)
_HIT_RELEVANCE = 0.5


def _log_search(db, query_text, mode, results, project_id, collection_name):
    """Best-effort read-path instrumentation (never raises into the caller).

    Writes one doc to `search_log` per search and bumps `surfaced_count` /
    `last_surfaced` on each returned pattern. This makes the READ side of shared
    memory measurable (search volume, hit rate, surfaced-vs-applied funnel) —
    usage_count alone only captures the APPLY side.
    """
    try:
        if not db.has_collection("search_log"):
            db.create_collection("search_log")  # lazy provision
        top = results[0] if results else None
        db.collection("search_log").insert({
            "query": query_text[:500],
            "project_id": project_id or None,
            "mode": mode,
            "count": len(results),
            "top_key": top["_key"] if top else None,
            "top_score": top.get("score") if top else None,
            "top_relevance": top.get("relevance") if top else None,
            "hit": bool(top and (top.get("relevance") or 0) >= _HIT_RELEVANCE),
            "result_keys": [r["_key"] for r in results],
            "created_at": datetime.datetime.now(datetime.timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        keys = [r["_key"] for r in results]
        if keys:
            db.aql.execute(
                "FOR k IN @keys FOR p IN @@coll FILTER p._key == k "
                "UPDATE p WITH { surfaced_count: (p.surfaced_count == null ? 0 : p.surfaced_count) + 1, "
                "last_surfaced: @now } IN @@coll",
                bind_vars={"keys": keys, "@coll": collection_name,
                           "now": datetime.datetime.now(datetime.timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ")})
    except Exception:  # noqa: BLE001 — instrumentation must never break search
        pass


@mcp_app.tool(
    name="pattern-search",
    description="""Hybrid semantic + keyword search over the shared-memory patterns.

    Pass a plain-text problem description; the server embeds it, fuses ANN vector
    similarity with BM25 full-text (Reciprocal Rank Fusion, k=60), and re-ranks by
    graded salience (importance + recency decay + usage). Returns only the top
    ranked patterns — no raw vectors.

    Falls back to BM25-only when embeddings are unavailable (no OPENAI_API_KEY) or
    the collection has no vector index yet. Use this instead of composing
    embed-text + AQL by hand.
    """,
)
async def pattern_search(
    query_text: str = Field(description="Free-text problem description to search for."),
    limit: int = Field(default=8, description="Max patterns to return (1-25)."),
    graph_expand: bool = Field(default=True, description="Also pull 1-hop pattern_relates_to "
                               "neighbors of the top semantic hits into the candidate pool (Phase 2)."),
    collection_name: str = Field(default="shared_patterns", description="Patterns collection."),
    view_name: str = Field(default="patterns_search", description="ArangoSearch view for BM25."),
    database_name: str = Field(default="", description="Target database (default: server default)."),
    model: str = Field(default="", description="Optional embedding model override."),
    project_id: str = Field(default="", description="Calling project id (from CLAUDE.md) — logged "
                            "for per-project read-path analytics; optional."),
):
    lim = max(1, min(int(limit), 25))
    try:
        db = arango_connector.get_db(database_name or None)
        coll = db.collection(collection_name)

        qvec = None
        mode = "bm25"
        if _has_vector_index(coll):
            try:
                embeddings, _model, _dim = await generate_embeddings([query_text], model)
                qvec = embeddings[0]
                mode = "hybrid"
            except Exception:  # noqa: BLE001 — embeddings optional; degrade to BM25
                qvec = None

        use_graph = (qvec is not None and graph_expand and db.has_collection("pattern_relates_to"))
        if use_graph:
            mode = "hybrid+graph"
            cursor = db.aql.execute(_HYBRID_GRAPH_AQL, bind_vars={
                "q": query_text, "qvec": qvec, "lim": lim,
                "@coll": collection_name, "@view": view_name})
        elif qvec is not None:
            cursor = db.aql.execute(_HYBRID_AQL, bind_vars={
                "q": query_text, "qvec": qvec, "lim": lim,
                "@coll": collection_name, "@view": view_name})
        else:
            cursor = db.aql.execute(_BM25_AQL, bind_vars={
                "q": query_text, "lim": lim, "@view": view_name})

        results = list(cursor)
        _log_search(db, query_text, mode, results, project_id, collection_name)
        return {"result": {"mode": mode, "count": len(results), "patterns": results}}
    except Exception as exc:  # noqa: BLE001
        return {"result": {"error": str(exc)}}


@mcp_app.tool(
    name="pattern-index",
    description="""Maintain the shared-memory graph for ONE just-saved pattern.

    Call this right after saving a pattern (pass its _key). Server-side, it:
      1. embeds the pattern's text into `embedding` if missing;
      2. links it to its top-K nearest neighbours via `pattern_relates_to`
         (cosine >= rel_sim);
      3. supersede check — if a neighbour is a near-duplicate (cosine >= sup_sim),
         the newer (by created_at) supersedes the older: adds a `pattern_supersedes`
         edge and demotes the older (superseded=true, importance=1) so it drops out
         of search.

    This replaces manual re-runs of the phase2/phase3 scripts for incremental saves.
    Cheap + deterministic (no LLM). LLM edges (pattern_addresses_requirement,
    requirement_depends_on) remain a periodic batch (scripts/phase2b_extract.py).
    Returns a small summary. Requires OPENAI_API_KEY for the embedding step.
    """,
)
async def pattern_index(
    document_key: str = Field(description="_key of the just-saved shared_patterns doc."),
    collection_name: str = Field(default="shared_patterns", description="Patterns collection."),
    rel_sim: float = Field(default=0.30, description="Min cosine to create a relates_to edge."),
    sup_sim: float = Field(default=0.90, description="Min cosine to treat as a near-duplicate/supersede."),
    top_k: int = Field(default=3, description="Neighbours to consider (1-10)."),
    database_name: str = Field(default="", description="Target database (default: server default)."),
    model: str = Field(default="", description="Optional embedding model override."),
):
    try:
        db = arango_connector.get_db(database_name or None)
        coll = db.collection(collection_name)
        doc = coll.get(document_key)
        if not doc:
            return {"result": {"error": f"document {document_key!r} not found"}}

        # 1. Ensure a REAL embedding. Re-embed if missing OR only a deferred placeholder
        #    is present (embedding_pending, from a save during an OpenAI outage); clear
        #    the flag once the real vector lands.
        embedded = False
        if not doc.get("embedding") or doc.get("embedding_pending"):
            text = "\n".join(str(doc[f]) for f in ("problem_description", "solution_summary")
                             if doc.get(f))
            if text.strip():
                vecs, _m, _d = await generate_embeddings([text], model)
                coll.update({"_key": document_key, "embedding": vecs[0],
                             "embedding_pending": False})
                doc["embedding"] = vecs[0]
                doc["embedding_pending"] = False
                embedded = True

        if not doc.get("embedding") or doc.get("embedding_pending") or not _has_vector_index(coll):
            return {"result": {"embedded": embedded, "relates_edges": 0, "superseded": None,
                               "note": "no real embedding or vector index; skipped graph maintenance"}}

        rel_edges, superseded = _maintain_graph(
            db, coll, collection_name, document_key, doc["embedding"],
            doc.get("created_at"), rel_sim, sup_sim, top_k, doc.get("project_id"))
        return {"result": {"embedded": embedded, "relates_edges": rel_edges,
                           "superseded": superseded}}
    except Exception as exc:  # noqa: BLE001
        return {"result": {"error": str(exc)}}


@mcp_app.tool(
    name="save-pattern",
    description="""Save a solved-problem pattern to shared memory — embed-THEN-insert.

    This is the correct save path when shared_patterns has a (non-sparse) vector
    index: the server embeds the text and inserts the document WITH its embedding
    in one step, so the insert satisfies the index (a plain insert-then-embed flow
    fails: the index rejects docs lacking the vector). It then maintains the graph
    (pattern_relates_to + supersede check), exactly like pattern-index.

    Generates a timestamped _key, sets usage_count=0 and last_used=created_at.
    Requires OPENAI_API_KEY when a vector index is present. Returns a small summary
    (no raw vectors). LLM edges remain a periodic batch (scripts/phase2b_extract.py).
    """,
)
async def save_pattern(
    problem_description: str = Field(description="One-sentence problem description."),
    solution_summary: str = Field(description="2-5 sentence solution, reusable across projects."),
    problem_category: str = Field(description="e.g. auth|api-design|data-model|testing|deployment|other."),
    project_id: str = Field(description="Originating project id (from CLAUDE.md)."),
    project_type: str = Field(default="other", description="Project type."),
    tags: List[str] = Field(default=[], description="2-5 keyword tags."),
    importance: int = Field(default=5, description="LLM-rated salience 1-10 (drives ranking)."),
    source_file: str = Field(default="", description="Relevant file:line, if any."),
    worked: bool = Field(default=True, description="Whether the solution was verified to work."),
    created_at: str = Field(default="", description="ISO timestamp; defaults to now (UTC)."),
    collection_name: str = Field(default="shared_patterns", description="Patterns collection."),
    database_name: str = Field(default="", description="Target database (default: server default)."),
    model: str = Field(default="", description="Optional embedding model override."),
    rel_sim: float = Field(default=0.30, description="Min cosine for a relates_to edge."),
    sup_sim: float = Field(default=0.90, description="Min cosine to treat as a near-duplicate."),
    top_k: int = Field(default=3, description="Neighbours to consider for graph edges."),
):
    try:
        db = arango_connector.get_db(database_name or None)
        coll = db.collection(collection_name)
        now = datetime.datetime.now(datetime.timezone.utc)
        created = created_at or now.strftime("%Y-%m-%dT%H:%M:%SZ")
        key = re.sub(r"[^A-Za-z0-9_-]", "-",
                     f"{project_id}_{problem_category}_{now.strftime('%Y%m%d_%H%M%S')}")[:250]

        # Embed BEFORE insert so the doc satisfies a non-sparse vector index.
        embedding, embed_error = None, None
        try:
            vecs, _m, _d = await generate_embeddings(
                [f"{problem_description}\n{solution_summary}"], model)
            embedding = vecs[0]
        except Exception as exc:  # noqa: BLE001
            embed_error = str(exc)

        doc = {"_key": key, "project_id": project_id, "project_type": project_type,
               "problem_category": problem_category, "problem_description": problem_description,
               "solution_summary": solution_summary, "tags": tags, "worked": worked,
               "created_at": created, "importance": importance, "usage_count": 0,
               "last_used": created, "source_file": source_file}
        pending = False
        if embedding is not None:
            doc["embedding"] = embedding
        elif _has_vector_index(coll):
            # A non-sparse vector index rejects embedding-less inserts, which would make
            # the whole save fail whenever OpenAI is unreachable (coupling every write to
            # an external API). Instead insert with a zero-mean PLACEHOLDER vector +
            # embedding_pending flag: the pattern is saved and immediately BM25-searchable,
            # and pattern-index / phase1b_setup.py backfill the real embedding (and
            # relates_to edges) later. The placeholder is ~orthogonal to real query
            # vectors, so it does not surface via vector search.
            dim = _vector_dim(coll)
            doc["embedding"] = [1.0 / dim] * dim
            doc["embedding_pending"] = True
            pending = True
        coll.insert(doc)

        # Provenance always; pass embedding=None when pending so the placeholder is not
        # used to build bogus KNN relates_to edges (provenance needs no embedding).
        rel_edges, superseded = _maintain_graph(
            db, coll, collection_name, key, (None if pending else embedding),
            created, rel_sim, sup_sim, top_k, project_id)
        result = {"_key": key, "embedded": embedding is not None,
                  "embedding_pending": pending,
                  "relates_edges": rel_edges, "superseded": superseded}
        if pending:
            result["note"] = (f"embedding deferred ({embed_error}); pattern saved and "
                              f"keyword-searchable now. Backfill with pattern-index on this "
                              f"_key (or re-run phase1b_setup.py).")
        return {"result": result}
    except Exception as exc:  # noqa: BLE001
        return {"result": {"error": str(exc)}}


@mcp_app.tool(
    name="save-drift-alert",
    description="""Upsert a PRD drift alert AND maintain its project provenance edge.

    Use this from /prd-sync instead of a raw upsert-document into drift_alerts: it
    guarantees the alert is linked to its project node via an alert_from_project
    edge (drift_alerts -> project_registry), auto-creating the project node if the
    project has never run /prd-sync -- so drift alerts and their projects never
    become orphan nodes in the memory graph.

    Idempotent on _key = <project_id>_<req_id>. Identity fields (project_id,
    req_id) are preserved across syncs; only the non-empty status/evidence fields
    passed are merged on re-detection. To close a gap, pass status='closed' with
    closed_at / closed_evidence.
    """,
)
async def save_drift_alert(
    project_id: str = Field(description="Originating project id (from CLAUDE.md)."),
    req_id: str = Field(description="Requirement id, e.g. REQ-007."),
    requirement: str = Field(default="", description="Requirement text."),
    classification: str = Field(default="", description="IMPLEMENTED|PARTIAL|MISSING|TEST-ONLY."),
    status: str = Field(default="open", description="open|closed."),
    evidence: str = Field(default="", description="file:line, or empty."),
    gap_description: str = Field(default="", description="What is missing/partial."),
    detected_at: str = Field(default="", description="ISO timestamp; defaults to now (UTC)."),
    closed_at: str = Field(default="", description="ISO timestamp when the gap was closed."),
    closed_evidence: str = Field(default="", description="file:line proving implementation."),
    collection_name: str = Field(default="drift_alerts", description="Alerts collection."),
    database_name: str = Field(default="", description="Target database (default: server default)."),
):
    try:
        db = arango_connector.get_db(database_name or None)
        if not db.has_collection(collection_name):
            return {"result": {"error": f"collection {collection_name!r} not found"}}
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        key = re.sub(r"[^A-Za-z0-9_-]", "-", f"{project_id}_{req_id}")[:250]

        full = {"_key": key, "project_id": project_id, "req_id": req_id,
                "requirement": requirement, "classification": classification,
                "status": status, "evidence": evidence,
                "gap_description": gap_description, "detected_at": detected_at or now}
        if status == "closed":
            full["closed_at"] = closed_at or now
            full["closed_evidence"] = closed_evidence
        # Merge subset: everything but identity, dropping empty strings so a
        # re-detect never blanks a previously-set field (matches the old
        # upsert-document search_fields/update_data semantics).
        upd = {k: v for k, v in full.items()
               if k not in ("_key", "project_id", "req_id") and v != ""}

        db.aql.execute("UPSERT { _key: @key } INSERT @full UPDATE @upd IN @@coll",
                       bind_vars={"key": key, "full": full, "upd": upd, "@coll": collection_name})

        prov = _ensure_provenance(db, "alert_from_project", f"{collection_name}/{key}",
                                  project_id, "alert_from_project")
        return {"result": {"_key": key, "status": status, "provenance_edge": prov}}
    except Exception as exc:  # noqa: BLE001
        return {"result": {"error": str(exc)}}


@mcp_app.tool(
    name="pattern-applied",
    description="""Record that one or more shared-memory patterns were APPLIED to solve a
    problem (not merely surfaced by a search). Bumps usage_count and refreshes last_used,
    which feed the /pattern-search graded ranking so genuinely-reused patterns rank higher
    over time.

    Call this right after you USE a pattern returned by /pattern-search -- pass the _key(s)
    you actually applied, NOT every result that was shown. This is the APPLY side of the
    read-path funnel: /pattern-search records what was surfaced; this records what was
    reused. One call, no AQL needed.
    """,
)
async def pattern_applied(
    keys: List[str] = Field(description="_key(s) of the pattern(s) actually applied."),
    collection_name: str = Field(default="shared_patterns", description="Patterns collection."),
    database_name: str = Field(default="", description="Target database (default: server default)."),
):
    try:
        if not keys:
            return {"result": {"error": "no keys provided"}}
        db = arango_connector.get_db(database_name or None)
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        updated = list(db.aql.execute(
            "FOR k IN @keys FOR p IN @@coll FILTER p._key == k "
            "UPDATE p WITH { usage_count: (p.usage_count == null ? 0 : p.usage_count) + 1, "
            "last_used: @now } IN @@coll "
            "RETURN { _key: NEW._key, usage_count: NEW.usage_count }",
            bind_vars={"keys": keys, "@coll": collection_name, "now": now}))
        missing = [k for k in keys if k not in [u["_key"] for u in updated]]
        return {"result": {"applied": updated, "count": len(updated),
                           "not_found": missing}}
    except Exception as exc:  # noqa: BLE001
        return {"result": {"error": str(exc)}}
