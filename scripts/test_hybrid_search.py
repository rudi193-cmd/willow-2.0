#!/usr/bin/env python3
"""
scripts/test_hybrid_search.py — Live CLI tool for hybrid_search against the real KB.
b17: RANK1  ΔΣ=42

Runs a query against the real willow_19 Postgres DB and shows ranked results
with scores from each retrieval leg (pgvector, BM25, RRF fusion).

Usage:
    python scripts/test_hybrid_search.py "your query here"
    python scripts/test_hybrid_search.py "grove fleet" --project hanuman --limit 10
    python scripts/test_hybrid_search.py "session memory" --temporal
    python scripts/test_hybrid_search.py "embed backfill" --bm25-only
    python scripts/test_hybrid_search.py "knowledge atom" --compare

Requires:
    - willow_19 Postgres DB running
    - Ollama with nomic-embed-text (only for pgvector leg)
    - rank_bm25 installed: pip install rank-bm25
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _truncate(s: str, n: int = 80) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s[:n] + "..." if len(s) > n else s


def _show_results(results: list[dict], score_field: str = "_rrf_score",
                  label: str = "Results") -> None:
    if not results:
        print(f"  (no results)")
        return
    print(f"\n{label} ({len(results)} hits):")
    print(f"  {'#':<3}  {'Score':<10}  {'ID':<12}  {'Title':<40}  Summary")
    print(f"  {'-'*3}  {'-'*10}  {'-'*12}  {'-'*40}  {'-'*40}")
    for i, r in enumerate(results):
        score = r.get(score_field, r.get("_rrf_score", 0.0))
        row_id = str(r.get("id", ""))[:12]
        title = _truncate(r.get("title") or "", 38)
        summary = _truncate(r.get("summary") or "", 40)
        temporal = ""
        if "_blended_score" in r:
            temporal = f"  [temp={r['_temporal_score']:.3f} blend={r['_blended_score']:.3f}]"
        print(f"  {i+1:<3}  {score:<10.5f}  {row_id:<12}  {title:<40}  {summary}{temporal}")


def main():
    ap = argparse.ArgumentParser(
        description="Test hybrid_search against the live Willow KB"
    )
    ap.add_argument("query", help="Natural language query")
    ap.add_argument("--project", default=None, help="Restrict to this project")
    ap.add_argument("--fork-id", default=None, help="Restrict to this fork_id")
    ap.add_argument("--limit", type=int, default=15, help="Max results (default 15)")
    ap.add_argument("--wide-k", type=int, default=30,
                    help="Candidates per leg before RRF (default 30)")
    ap.add_argument("--temporal", action="store_true",
                    help="Apply temporal re-ranking (half-life decay)")
    ap.add_argument("--decay-days", type=float, default=30.0,
                    help="Half-life for temporal decay in days (default 30)")
    ap.add_argument("--bm25-only", action="store_true",
                    help="Run BM25 leg only (no pgvector)")
    ap.add_argument("--compare", action="store_true",
                    help="Show all three: BM25-only, pgvector-only, and hybrid")
    args = ap.parse_args()

    from core.pg_bridge import PgBridge, embed  # type: ignore
    from willow.ranking.hybrid import hybrid_search, bm25_search, _pgvector_search_raw

    pg = PgBridge()
    query = args.query

    print(f"\nQuery: {query!r}")
    print(f"Project filter: {args.project or '(none)'}")
    print(f"Limit: {args.limit}  wide_k: {args.wide_k}  temporal: {args.temporal}")

    if args.compare:
        # --- BM25 leg ---
        t0 = time.time()
        bm25_results = bm25_search(
            query, pg, project=args.project, fork_id=args.fork_id, limit=args.limit
        )
        t_bm25 = time.time() - t0
        _show_results(bm25_results, score_field="_rrf_score", label=f"BM25-only ({t_bm25*1000:.0f}ms)")

        # --- pgvector leg ---
        t0 = time.time()
        vec = embed(query)
        vec_results = []
        if vec:
            vec_results = _pgvector_search_raw(
                pg, vec, args.project, args.fork_id, False, args.limit
            )
        t_vec = time.time() - t0
        _show_results(vec_results, score_field="_cosine_sim", label=f"pgvector-only ({t_vec*1000:.0f}ms)")

        # --- Hybrid ---
        t0 = time.time()
        hybrid_results = hybrid_search(
            query, pg,
            project=args.project, fork_id=args.fork_id,
            limit=args.limit, wide_k=args.wide_k,
            temporal=args.temporal,
            temporal_decay_days=args.decay_days,
        )
        t_hybrid = time.time() - t0
        score_f = "_blended_score" if args.temporal else "_rrf_score"
        _show_results(hybrid_results, score_field=score_f, label=f"Hybrid RRF ({t_hybrid*1000:.0f}ms)")

    elif args.bm25_only:
        t0 = time.time()
        results = bm25_search(
            query, pg, project=args.project, fork_id=args.fork_id, limit=args.limit
        )
        t = time.time() - t0
        _show_results(results, label=f"BM25-only ({t*1000:.0f}ms)")

    else:
        t0 = time.time()
        results = hybrid_search(
            query, pg,
            project=args.project, fork_id=args.fork_id,
            limit=args.limit, wide_k=args.wide_k,
            temporal=args.temporal,
            temporal_decay_days=args.decay_days,
        )
        t = time.time() - t0
        score_f = "_blended_score" if args.temporal else "_rrf_score"
        _show_results(results, score_field=score_f,
                      label=f"Hybrid RRF{' + temporal' if args.temporal else ''} ({t*1000:.0f}ms)")

    pg.close()
    print()


if __name__ == "__main__":
    main()
