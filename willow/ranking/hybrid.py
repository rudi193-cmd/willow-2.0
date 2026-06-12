"""
willow/ranking/hybrid.py — Hybrid pgvector cosine + BM25 RRF search.
b17: RANK1  ΔΣ=42

Ported and adapted from m4cd4r4/claude-echoes (MIT License).

Original source: benchmarks/run_longmemeval.py::EchoesRetriever.search_hybrid
and server/app.py::search endpoint.

Willow adaptations:
  - Works against Willow's `knowledge` table (not claude-echoes `messages`)
  - Searchable text = title + " " + summary (not full content)
  - Respects project, fork_id, and invalid_at filters
  - Respects the `weight` column as a post-RRF signal multiplier
  - Uses Willow's own PgBridge and embed() rather than direct asyncpg
  - BM25 is computed in-process using rank_bm25 (lazy install guard included)
  - Falls back gracefully: no embed → pure BM25; no rank_bm25 → pure pgvector

RRF formula (Cormack et al. 2009):
    score(doc) = Σ  1 / (k + rank_i)   for each retrieval method i
    k = 60  (standard constant; higher k reduces rank sensitivity)

Temporal re-ranking (half-life decay):
    temporal_score(doc) = 0.5 ^ (age_days / decay_days)
    blended = (1 - α) * rrf_score_norm + α * temporal_score
    α = temporal_weight (default 0.15)
"""
from __future__ import annotations

import re
import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.pg_bridge import PgBridge

# ── Constants ─────────────────────────────────────────────────────────────────

RRF_K: int = 60          # standard RRF constant from Cormack et al. 2009
WIDE_K: int = 30         # candidates per ranker before fusion
MAX_CONTENT_CHARS: int = 8000  # nomic context window guard

# ── Tokenizer (mirrors claude-echoes _tokenize) ───────────────────────────────

_TOK_RE = re.compile(r"[a-z0-9]+")

def _tokenize(text: str) -> list[str]:
    """
    Simple BM25 tokenizer: lowercase, alphanumeric tokens, length 2-30.
    No stemming — keeps results auditable and deterministic.
    Mirrors claude-echoes' _tokenize() exactly.
    """
    text = (text or "").lower()
    tokens = _TOK_RE.findall(text)
    return [t for t in tokens if 2 <= len(t) <= 30]


def _row_text(row: dict) -> str:
    """Concatenate the searchable text surface of a knowledge atom."""
    parts = [row.get("title") or "", row.get("summary") or ""]
    content = row.get("content")
    if isinstance(content, dict):
        for key in ("tags", "keywords", "evidence", "source_id"):
            value = content.get(key)
            if isinstance(value, list):
                parts.extend(str(item) for item in value)
            elif value:
                parts.append(str(value))
    return " ".join(p for p in parts if p)


# ── BM25 index (lazy import guard) ───────────────────────────────────────────

def _build_bm25(rows: list[dict]):
    """
    Build a BM25Okapi index over the given rows.
    Returns (bm25_obj, local_indices) where local_indices maps bm25 position
    back to list position in `rows`. Falls back to a small in-process lexical
    scorer when rank_bm25 is unavailable so hybrid search keeps an exact-token
    leg in minimal runtime environments.
    """
    corpus = [_tokenize(_row_text(r)) for r in rows]
    try:
        from rank_bm25 import BM25Okapi  # type: ignore
        return BM25Okapi(corpus)
    except ImportError:
        return _SimpleLexicalRanker(corpus)


class _SimpleLexicalRanker:
    """Tiny IDF-weighted fallback with the same get_scores() shape as BM25Okapi."""

    def __init__(self, corpus: list[list[str]]) -> None:
        self.corpus = corpus
        doc_count = max(len(corpus), 1)
        dfs: dict[str, int] = {}
        for doc in corpus:
            for token in set(doc):
                dfs[token] = dfs.get(token, 0) + 1
        self.idf = {
            token: math.log((doc_count + 1) / (df + 1)) + 1.0
            for token, df in dfs.items()
        }

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        scores: list[float] = []
        query = [token for token in query_tokens if token]
        for doc in self.corpus:
            if not doc:
                scores.append(0.0)
                continue
            freqs: dict[str, int] = {}
            for token in doc:
                freqs[token] = freqs.get(token, 0) + 1
            score = sum(self.idf.get(token, 0.0) * freqs.get(token, 0) for token in query)
            scores.append(score / math.sqrt(len(doc)))
        return scores


# ── pgvector leg ─────────────────────────────────────────────────────────────

def _pgvector_search(
    pg: "PgBridge",
    query_vec: list[float],
    *,
    project: Optional[str],
    fork_id: Optional[str],
    include_invalid: bool,
    wide_k: int,
) -> list[dict]:
    """
    ANN search using the HNSW index on knowledge.embedding.
    Returns up to wide_k rows ordered by cosine distance ascending.
    """
    vec_str = str(query_vec)
    filters = ["embedding IS NOT NULL"]
    params: list = [vec_str]

    if not include_invalid:
        filters.append("invalid_at IS NULL")
    if project:
        filters.append("project = %s")
        params.append(project)
    if fork_id:
        filters.append("fork_id = %s")
        params.append(fork_id)

    where = " AND ".join(filters)
    params.append(wide_k)

    import psycopg2.extras  # type: ignore

    pg._ensure_conn()
    with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"SELECT *, 1 - (embedding <=> %s::vector) AS _cosine_sim"
            f" FROM knowledge WHERE {where}"
            f" ORDER BY embedding <=> %s::vector ASC LIMIT %s",
            [vec_str, vec_str, wide_k] if not project and not fork_id
            else params[:1] + params[1:],
        )
        return [dict(r) for r in cur.fetchall()]


def _pgvector_search_raw(
    pg: "PgBridge",
    query_vec: list[float],
    project: Optional[str],
    fork_id: Optional[str],
    include_invalid: bool,
    wide_k: int,
    tier: Optional[str] = None,
    exclude_search_noise: bool = True,
    exclude_superseded: bool = True,
) -> list[dict]:
    """Clean wrapper around the ANN search to avoid param duplication."""
    vec_str = str(query_vec)
    filters = ["embedding IS NOT NULL"]
    where_params: list = []

    if not include_invalid:
        filters.append("invalid_at IS NULL")
    if project:
        filters.append("project = %s")
        where_params.append(project)
    if fork_id:
        filters.append("fork_id = %s")
        where_params.append(fork_id)
    pg._knowledge_retrieval_filters(
        filters,
        where_params,
        tier=tier,
        exclude_search_noise=exclude_search_noise,
        exclude_superseded=exclude_superseded,
    )

    where = " AND ".join(filters)

    import psycopg2.extras  # type: ignore

    pg._ensure_conn()
    with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"SELECT *, 1 - (embedding <=> %s::vector) AS _cosine_sim"
            f" FROM knowledge WHERE {where}"
            f" ORDER BY embedding <=> %s::vector ASC LIMIT %s",
            [vec_str] + where_params + [vec_str, wide_k],
        )
        return [dict(r) for r in cur.fetchall()]


# ── BM25 leg over DB-fetched candidates ──────────────────────────────────────

def _bm25_search(
    pg: "PgBridge",
    query_tokens: list[str],
    project: Optional[str],
    fork_id: Optional[str],
    include_invalid: bool,
    wide_k: int,
    tier: Optional[str] = None,
    exclude_search_noise: bool = True,
    exclude_superseded: bool = True,
) -> list[dict]:
    """
    BM25 search over knowledge table.

    Strategy: pull a reasonable candidate pool from Postgres (the larger of
    wide_k*3 or 200 rows, filtered by project/fork), build a BM25 index
    in-process, score against the query, return top wide_k.

    This avoids needing a PostgreSQL full-text ranking function and keeps
    BM25 parameters in Python where they're tunable.
    """
    candidate_limit = max(wide_k * 10, 1000)

    filters = []
    params: list = []

    if not include_invalid:
        filters.append("invalid_at IS NULL")
    if project:
        filters.append("project = %s")
        params.append(project)
    if fork_id:
        filters.append("fork_id = %s")
        params.append(fork_id)
    pg._knowledge_retrieval_filters(
        filters,
        params,
        tier=tier,
        exclude_search_noise=exclude_search_noise,
        exclude_superseded=exclude_superseded,
    )
    token_predicates = []
    for token in dict.fromkeys(query_tokens[:8]):
        like = f"%{token}%"
        token_predicates.append(
            "(title ILIKE %s OR summary ILIKE %s OR content::text ILIKE %s)"
        )
        params.extend([like, like, like])
    if token_predicates:
        filters.append("(" + " OR ".join(token_predicates) + ")")

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    params.append(candidate_limit)

    import psycopg2.extras  # type: ignore

    pg._ensure_conn()
    with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"SELECT * FROM knowledge {where} LIMIT %s",
            params,
        )
        candidates = [dict(r) for r in cur.fetchall()]

    if not candidates or not query_tokens:
        return []

    bm25 = _build_bm25(candidates)
    scores = bm25.get_scores(query_tokens)

    # Sort by score descending, return top wide_k
    ranked = sorted(range(len(scores)), key=lambda i: -scores[i])
    return [candidates[i] for i in ranked[:wide_k] if scores[i] > 0.0]


# ── RRF fusion ────────────────────────────────────────────────────────────────

def _rrf_fuse(
    ranked_lists: list[list[dict]],
    k: int = RRF_K,
    weight_col: bool = True,
) -> list[dict]:
    """
    Reciprocal Rank Fusion over N ranked lists.

    RRF score(doc) = Σ_i  1 / (k + rank_i)
    where rank_i is the 1-indexed position of doc in list i.

    If weight_col=True, the atom's `weight` field (default 1.0) is applied
    as a multiplier on the final fused score. This lets Willow's existing
    weight-based promotion continue to function.

    Returns all unique docs sorted by fused score descending.
    """
    scores: dict[str, dict] = {}

    for ranked in ranked_lists:
        for rank, row in enumerate(ranked):
            doc_id = row["id"]
            if doc_id not in scores:
                scores[doc_id] = {"row": row, "rrf": 0.0}
            scores[doc_id]["rrf"] += 1.0 / (k + rank + 1)

    results = []
    for doc_id, entry in scores.items():
        row = entry["row"]
        rrf = entry["rrf"]
        if weight_col:
            w = float(row.get("weight") or 1.0)
            rrf *= w
        results.append({**row, "_rrf_score": rrf})

    results.sort(key=lambda r: -r["_rrf_score"])
    return results


def _apply_lexical_coverage_bias(results: list[dict], query_tokens: list[str]) -> list[dict]:
    """Prefer fused hits that cover more of the user's explicit query tokens."""
    unique_query = list(dict.fromkeys(query_tokens))
    if not results or not unique_query:
        return results

    biased = []
    query_count = len(unique_query)
    for row in results:
        row_tokens = set(_tokenize(_row_text(row)))
        covered = sum(1 for token in unique_query if token in row_tokens)
        coverage = covered / query_count
        multiplier = 0.25 + (0.75 * coverage) + (0.75 * coverage * coverage)
        hybrid_score = float(row.get("_rrf_score") or 0.0) * multiplier
        biased.append({
            **row,
            "_lexical_coverage": round(coverage, 4),
            "_hybrid_score": hybrid_score,
        })

    biased.sort(key=lambda r: -r["_hybrid_score"])
    return biased


# ── Temporal re-ranking ───────────────────────────────────────────────────────

def temporal_rerank(
    results: list[dict],
    decay_days: float = 30.0,
    temporal_weight: float = 0.15,
) -> list[dict]:
    """
    Boost recent atoms using exponential half-life decay.

    temporal_score = 0.5 ^ (age_days / decay_days)
      → score = 1.0   when age_days = 0       (just written)
      → score = 0.5   when age_days = decay_days (default 30d)
      → score = 0.25  at 2 * decay_days

    Blended final score:
        blended = (1 - temporal_weight) * rrf_norm + temporal_weight * temporal_score

    rrf_norm is the RRF score normalized to [0, 1] across this result set.
    temporal_weight=0.15 matches the claude-echoes default that gave the best
    benchmark results — conservative enough not to hurt non-temporal queries.

    Ported from claude-echoes' search_hybrid_temporal() and search_temporal().
    """
    if not results:
        return results

    now = datetime.now(timezone.utc)

    # Gather RRF scores for normalization
    rrf_scores = [float(r.get("_rrf_score") or 0.0) for r in results]
    rrf_min = min(rrf_scores)
    rrf_max = max(rrf_scores)
    rrf_range = rrf_max - rrf_min if rrf_max > rrf_min else 1.0

    out = []
    for row, rrf in zip(results, rrf_scores):
        rrf_norm = (rrf - rrf_min) / rrf_range

        # Age from created_at or valid_at
        ts = row.get("created_at") or row.get("valid_at")
        if ts is not None:
            if isinstance(ts, str):
                try:
                    from dateutil import parser as _dp  # type: ignore
                    ts = _dp.parse(ts)
                except Exception:
                    ts = None
            if ts is not None and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

        if ts is not None:
            age_days = max((now - ts).total_seconds() / 86400.0, 0.0)
            temporal_score = 0.5 ** (age_days / decay_days)
        else:
            temporal_score = 0.5  # no timestamp: treat as middling age

        blended = (1.0 - temporal_weight) * rrf_norm + temporal_weight * temporal_score
        out.append({**row, "_temporal_score": round(temporal_score, 4),
                    "_blended_score": round(blended, 4)})

    out.sort(key=lambda r: -r["_blended_score"])
    return out


# ── BM25-only search (standalone utility) ────────────────────────────────────

def bm25_search(
    query: str,
    pg: "PgBridge",
    *,
    project: Optional[str] = None,
    fork_id: Optional[str] = None,
    include_invalid: bool = False,
    limit: int = 20,
) -> list[dict]:
    """
    Pure BM25 keyword search over the knowledge table.

    Useful for:
    - Queries with rare exact terms that cosine distance misses
    - Debugging: comparing BM25 leg results against vector results
    - Lightweight search when Ollama is unavailable

    Returns atoms sorted by BM25 score descending, with `_bm25_score` field.
    """
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    try:
        rows = _bm25_search(pg, query_tokens, project, fork_id, include_invalid, limit)
        return rows
    except ImportError:
        # rank_bm25 not installed — fall back to ILIKE
        return pg.knowledge_search(query, project=project,
                                   include_invalid=include_invalid, limit=limit)


# ── Main entry point ──────────────────────────────────────────────────────────

def hybrid_search(
    query: str,
    pg: "PgBridge",
    *,
    project: Optional[str] = None,
    fork_id: Optional[str] = None,
    include_invalid: bool = False,
    limit: int = 20,
    wide_k: int = WIDE_K,
    rrf_k: int = RRF_K,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3,
    temporal: bool = False,
    temporal_decay_days: float = 30.0,
    temporal_weight: float = 0.15,
    tier: Optional[str] = None,
    exclude_search_noise: bool = True,
    exclude_superseded: bool = True,
) -> list[dict]:
    """
    Hybrid pgvector cosine + BM25 keyword search with RRF fusion.

    Pipeline:
      1. Embed query via Ollama (nomic-embed-text, 768-dim) → pgvector ANN
      2. Tokenize query → BM25 over candidate pool from DB
      3. RRF fusion of both ranked lists (k=60)
      4. Optional temporal re-ranking (half-life decay on created_at)
      5. Return top `limit` atoms with `_rrf_score` (and `_blended_score` if temporal)

    Fallback chain:
      - embed() fails → BM25-only (no pgvector leg)
      - rank_bm25 not installed → pgvector-only (no BM25 leg)
      - both fail → pg.knowledge_search() (ILIKE)

    Parameters
    ----------
    query : str
        Natural language query.
    pg : PgBridge
        Willow Postgres bridge. Caller owns the lifecycle.
    project : str, optional
        Restrict to atoms with this project value.
    fork_id : str, optional
        Restrict to atoms with this fork_id.
    include_invalid : bool
        If True, include atoms where invalid_at IS NOT NULL.
    limit : int
        Max results to return (default 20).
    wide_k : int
        Candidates per leg before fusion (default 30). Higher = more recall
        at cost of in-process BM25 work.
    rrf_k : int
        RRF k constant (default 60 from Cormack et al. 2009).
    vector_weight : float
        Not used in RRF fusion (RRF is rank-based not score-based), but
        reserved for weighted-RRF experiments. Currently both legs have
        equal weight in the RRF sum.
    bm25_weight : float
        See vector_weight. Reserved.
    temporal : bool
        If True, apply temporal_rerank() after RRF fusion.
    temporal_decay_days : float
        Half-life in days for temporal decay (default 30).
    temporal_weight : float
        Blend factor for temporal score (default 0.15, matches claude-echoes
        optimal benchmark config).

    Returns
    -------
    list[dict]
        Atoms sorted by fused score (descending), with added fields:
          _rrf_score: float        — raw RRF fusion score
          _blended_score: float    — if temporal=True, the blended score
          _temporal_score: float   — if temporal=True, the decay score
    """
    from core.pg_bridge import embed  # type: ignore

    ranked_lists: list[list[dict]] = []

    # --- Leg 1: pgvector ANN ---
    try:
        query_vec = embed(query)
        if query_vec is not None:
            vec_rows = _pgvector_search_raw(
                pg, query_vec, project, fork_id, include_invalid, wide_k,
                tier=tier,
                exclude_search_noise=exclude_search_noise,
                exclude_superseded=exclude_superseded,
            )
            if vec_rows:
                ranked_lists.append(vec_rows)
    except Exception:
        pass  # Ollama down or table issue — continue to BM25

    # --- Leg 2: BM25 ---
    query_tokens = _tokenize(query)
    if query_tokens:
        try:
            bm25_rows = _bm25_search(
                pg, query_tokens, project, fork_id, include_invalid, wide_k,
                tier=tier,
                exclude_search_noise=exclude_search_noise,
                exclude_superseded=exclude_superseded,
            )
            if bm25_rows:
                ranked_lists.append(bm25_rows)
        except ImportError:
            pass  # rank_bm25 not installed
        except Exception:
            pass

    # --- Fallback: ILIKE ---
    if not ranked_lists:
        return pg.knowledge_search(query, project=project,
                                   include_invalid=include_invalid, limit=limit,
                                   tier=tier,
                                   exclude_search_noise=exclude_search_noise,
                                   exclude_superseded=exclude_superseded)

    # --- RRF fusion ---
    fused = _rrf_fuse(ranked_lists, k=rrf_k, weight_col=True)
    fused = _apply_lexical_coverage_bias(fused, query_tokens)

    # --- Temporal re-ranking ---
    if temporal:
        fused = temporal_rerank(fused, decay_days=temporal_decay_days,
                                temporal_weight=temporal_weight)

    return fused[:limit]
