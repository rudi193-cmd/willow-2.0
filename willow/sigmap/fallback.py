"""
willow/sigmap/fallback.py — Multi-level search fallback chain.
b17: SMAP2  ΔΣ=42

Steal track: samballington/CodeWise  (MIT License)

CodeWise runs a cascading strategy chain across hybrid→vector→bm25→file→ILIKE.
This module adapts that pattern to Willow's knowledge table, wiring it directly
onto PgBridge + the existing willow/ranking/hybrid.py infrastructure.

Chain (each level tried only if previous returns < threshold results):
    1. pgvector ANN          — HNSW cosine, fast approximate recall
    2. BM25 hybrid (RRF)     — existing hybrid_search() in willow/ranking/hybrid.py
    3. AST symbol exact match — sigmap indexer signatures via ILIKE on content->>'sigs'
    4. ILIKE full-text        — pg.knowledge_search() last-resort

Results from whichever level fires are returned as FallbackResult dicts with
metadata indicating which level triggered and scores at each level.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.pg_bridge import PgBridge

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────

# If a level returns at least this many results, stop cascading.
DEFAULT_THRESHOLD: int = 3

# Candidates to fetch per level before threshold check.
WIDE_K: int = 30


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class FallbackResult:
    """A knowledge atom returned by the fallback chain."""

    # Standard knowledge fields
    id: str
    title: str
    summary: str
    project: str
    weight: float

    # Provenance from the chain
    level: int          # 1=pgvector, 2=hybrid, 3=ast-symbol, 4=ilike
    level_name: str     # human-readable name of the triggering level
    score: float        # level-specific score (cosine sim, rrf, bm25, 0.0 for ilike)

    # Passthrough — any extra columns from the DB row
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_row(
        cls,
        row: dict,
        *,
        level: int,
        level_name: str,
        score: float,
    ) -> "FallbackResult":
        return cls(
            id=str(row.get("id", "")),
            title=row.get("title") or "",
            summary=row.get("summary") or "",
            project=row.get("project") or "global",
            weight=float(row.get("weight") or 1.0),
            level=level,
            level_name=level_name,
            score=score,
            extra={
                k: v for k, v in row.items()
                if k not in ("id", "title", "summary", "project", "weight")
            },
        )


# ── Level implementations ─────────────────────────────────────────────────────

def _level1_pgvector(
    pg: "PgBridge",
    query: str,
    project: Optional[str],
    fork_id: Optional[str],
    wide_k: int,
) -> list[FallbackResult]:
    """
    Level 1: pgvector HNSW ANN search.

    Uses Ollama nomic-embed-text (768-dim) to embed the query then does a
    cosine ANN scan over knowledge.embedding via the HNSW index.
    Returns up to wide_k results ordered by cosine similarity descending.
    """
    try:
        from core.pg_bridge import embed  # type: ignore
        import psycopg2.extras  # type: ignore

        query_vec = embed(query)
        if query_vec is None:
            return []

        vec_str = str(query_vec)
        filters = ["embedding IS NOT NULL", "invalid_at IS NULL"]
        where_params: list = []

        if project:
            filters.append("project = %s")
            where_params.append(project)
        if fork_id:
            filters.append("fork_id = %s")
            where_params.append(fork_id)

        where = " AND ".join(filters)

        pg._ensure_conn()
        with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT *, 1 - (embedding <=> %s::vector) AS _cosine_sim"
                f" FROM knowledge WHERE {where}"
                f" ORDER BY embedding <=> %s::vector ASC LIMIT %s",
                [vec_str] + where_params + [vec_str, wide_k],
            )
            rows = [dict(r) for r in cur.fetchall()]

        return [
            FallbackResult.from_row(
                r, level=1, level_name="pgvector",
                score=float(r.get("_cosine_sim") or 0.0),
            )
            for r in rows
        ]
    except Exception as exc:
        logger.debug("Level 1 (pgvector) failed: %s", exc)
        return []


def _level2_hybrid(
    pg: "PgBridge",
    query: str,
    project: Optional[str],
    fork_id: Optional[str],
    wide_k: int,
) -> list[FallbackResult]:
    """
    Level 2: BM25 + pgvector RRF hybrid (willow/ranking/hybrid.py).

    Runs both vector and BM25 legs and fuses with Reciprocal Rank Fusion.
    More accurate than raw ANN but slower (candidate pool fetch + in-process BM25).
    """
    try:
        from willow.ranking.hybrid import hybrid_search  # type: ignore

        rows = hybrid_search(
            query, pg,
            project=project,
            fork_id=fork_id,
            include_invalid=False,
            limit=wide_k,
            wide_k=wide_k,
        )
        return [
            FallbackResult.from_row(
                r, level=2, level_name="hybrid-rrf",
                score=float(r.get("_rrf_score") or 0.0),
            )
            for r in rows
        ]
    except Exception as exc:
        logger.debug("Level 2 (hybrid) failed: %s", exc)
        return []


def _level3_ast_symbol(
    pg: "PgBridge",
    query: str,
    project: Optional[str],
    fork_id: Optional[str],
    wide_k: int,
) -> list[FallbackResult]:
    """
    Level 3: AST symbol exact match.

    Searches the knowledge table for atoms whose content JSONB contains a
    'sigs' array with an element matching the query token(s).  This catches
    exact function/class name lookups that semantic search can miss.

    The sigmap indexer writes atoms with content->>'sigs' as a JSON array of
    signature strings.  We use ILIKE against the JSON text representation for
    a deterministic, index-free scan that's still fast on the knowledge table
    (which is at most ~50k rows in typical Willow deployments).
    """
    try:
        import psycopg2.extras  # type: ignore

        # Normalise to the most query-specific token (longest word)
        words = [w for w in query.split() if len(w) > 2]
        if not words:
            return []
        token = max(words, key=len)

        filters = ["invalid_at IS NULL", "content IS NOT NULL",
                   "content::text ILIKE %s"]
        params: list = [f"%{token}%"]

        if project:
            filters.append("project = %s")
            params.append(project)
        if fork_id:
            filters.append("fork_id = %s")
            params.append(fork_id)

        where = " AND ".join(filters)
        params.append(wide_k)

        pg._ensure_conn()
        with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM knowledge WHERE {where} LIMIT %s",
                params,
            )
            rows = [dict(r) for r in cur.fetchall()]

        return [
            FallbackResult.from_row(
                r, level=3, level_name="ast-symbol",
                score=1.0,          # deterministic hit — no gradient score
            )
            for r in rows
        ]
    except Exception as exc:
        logger.debug("Level 3 (ast-symbol) failed: %s", exc)
        return []


def _level4_ilike(
    pg: "PgBridge",
    query: str,
    project: Optional[str],
    wide_k: int,
) -> list[FallbackResult]:
    """
    Level 4: ILIKE full-text last-resort.

    Calls pg.knowledge_search() which does ILIKE on title + summary.
    No scores — all results get score=0.0 and are ordered by weight DESC.
    """
    try:
        rows = pg.knowledge_search(
            query, project=project, include_invalid=False, limit=wide_k
        )
        return [
            FallbackResult.from_row(
                r if isinstance(r, dict) else dict(r),
                level=4, level_name="ilike",
                score=0.0,
            )
            for r in rows
        ]
    except Exception as exc:
        logger.debug("Level 4 (ilike) failed: %s", exc)
        return []


# ── Main entry point ──────────────────────────────────────────────────────────

def fallback_search(
    query: str,
    pg: "PgBridge",
    *,
    project: Optional[str] = None,
    fork_id: Optional[str] = None,
    limit: int = 20,
    threshold: int = DEFAULT_THRESHOLD,
    wide_k: int = WIDE_K,
    start_level: int = 1,
) -> list[FallbackResult]:
    """
    Multi-level search fallback chain for Willow's knowledge table.

    Each level is attempted only if the previous level returned fewer than
    `threshold` results.  This keeps the happy path (pgvector ANN) fast while
    guaranteeing a result even if Ollama is down or the query is an exact
    identifier that semantic search scores poorly.

    Parameters
    ----------
    query : str
        Natural language or symbol query.
    pg : PgBridge
        Caller-owned PgBridge instance.
    project : str, optional
        Restrict to atoms with this project value.
    fork_id : str, optional
        Restrict to atoms with this fork_id.
    limit : int
        Max results to return from whichever level fires (default 20).
    threshold : int
        Minimum result count that satisfies a level (default 3).
        If a level returns >= threshold results, the chain stops.
    wide_k : int
        Candidates to fetch per level (default 30).
    start_level : int
        Skip levels below this value (1=run all, 2=skip pgvector, etc.).
        Useful for callers that know Ollama is unavailable.

    Returns
    -------
    list[FallbackResult]
        Results from the first level that meets the threshold, or all results
        from the last level tried if none met it.  Never raises.

    Chain
    -----
        Level 1  pgvector ANN       — HNSW cosine, requires Ollama + embeddings
        Level 2  BM25 hybrid (RRF)  — rank_bm25 + pgvector, more accurate
        Level 3  AST symbol ILIKE   — exact function/class name in content JSON
        Level 4  ILIKE              — title/summary full-text, always available
    """
    levels = [
        (1, lambda: _level1_pgvector(pg, query, project, fork_id, wide_k)),
        (2, lambda: _level2_hybrid(pg, query, project, fork_id, wide_k)),
        (3, lambda: _level3_ast_symbol(pg, query, project, fork_id, wide_k)),
        (4, lambda: _level4_ilike(pg, query, project, wide_k)),
    ]

    last_results: list[FallbackResult] = []

    for level_num, level_fn in levels:
        if level_num < start_level:
            continue

        results = level_fn()
        logger.debug(
            "fallback_search level=%d returned %d results for query=%r",
            level_num, len(results), query,
        )

        if results:
            last_results = results
            if len(results) >= threshold:
                logger.info(
                    "fallback_search satisfied at level %d (%s): %d results",
                    level_num,
                    results[0].level_name,
                    len(results),
                )
                return results[:limit]
        # else: keep going — level returned nothing

    # Exhausted all levels — return whatever the last level gave us
    if last_results:
        logger.info(
            "fallback_search exhausted chain, returning %d results from level %d",
            len(last_results), last_results[0].level,
        )
    else:
        logger.warning("fallback_search: all levels returned empty for query=%r", query)

    return last_results[:limit]
