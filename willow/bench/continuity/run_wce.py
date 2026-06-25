#!/usr/bin/env python3
"""
run_wce.py — Willow Continuity Eval MVP: cold-relevant recall probe.
b17: WCE1  ΔΣ=42

What this measures
------------------
The live ranker (willow/ranking/hybrid.py) multiplies its fused RRF score by the
atom's `weight` column — a rich-get-richer signal driven by visit_count + recency
(see core/pg_bridge.py weight formulas). The diagnosis (KB 270F089E) is that this
multiplier buries cold-but-relevant memory: an atom that is genuinely on-topic but
rarely visited / not recently touched loses to a warmer, less-relevant neighbour.

This probe quantifies that burial and runs the counterfactual the operator asked for:
does turning the weight multiplier OFF (weight_col=False) raise recall of the
cold-but-relevant atoms?

Method (offline, no paid calls — embeds via local Ollama nomic-embed-text)
-------------------------------------------------------------------------
For each probe query:
  1. ORACLE (recency-blind ground truth): embed the query, score every visible
     atom by raw cosine similarity. "Relevant" = top oracle_n by cosine that also
     clear a cosine floor. This deliberately ignores weight/recency/visit_count.
  2. COLD subset: of the relevant atoms, the "cold" ones are those with low
     temperature — visit_count <= cold_visit_max AND (never visited OR last_visited
     older than cold_age_days). These are exactly what the multiplier should not
     bury but does.
  3. LIVE RETRIEVAL, both settings: run hybrid_search(query, limit=k) with
     weight_col=True (current live) and weight_col=False (counterfactual).
  4. METRIC: cold-relevant recall@k = |cold_relevant ∩ top_k| / |cold_relevant|,
     reported per setting plus the lift (unweighted − weighted).

The oracle's visibility filters (invalid_at IS NULL, NOT search_noise, tier !=
superseded) match hybrid_search's defaults so the comparison is apples-to-apples:
an atom the ranker can never return is never counted as relevant.

Usage
-----
  python3 willow/bench/continuity/run_wce.py
  python3 willow/bench/continuity/run_wce.py --k 10 --oracle-n 20 --cosine-floor 0.5
  python3 willow/bench/continuity/run_wce.py --cold-visit-max 1 --cold-age-days 30
  python3 willow/bench/continuity/run_wce.py --queries path/to/queries.json --project willow

Output
------
  Prints a per-query + aggregate summary table.
  Writes runs/wce_<timestamp>.json with the full result vector.

Open knobs (handoff questions, intentionally exposed as CLI flags, not hard-coded):
  --cosine-floor / --oracle-n : what counts as "relevant" (relevance threshold)
  --cold-visit-max / --cold-age-days : what counts as "cold" (temperature threshold)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

BENCH_DIR = Path(__file__).resolve().parent
WILLOW_ROOT = Path(os.environ.get("WILLOW_ROOT", str(BENCH_DIR.parent.parent.parent)))
DEFAULT_QUERIES = BENCH_DIR / "wce_queries.json"
RUNS_DIR = BENCH_DIR / "runs"

sys.path.insert(0, str(WILLOW_ROOT))

from core.pg_bridge import PgBridge  # noqa: E402
from core.embedder import embed  # noqa: E402
from willow.ranking.hybrid import WEIGHT_MODES, hybrid_search  # noqa: E402

import psycopg2.extras  # noqa: E402


# ── Oracle: recency-blind cosine relevance ────────────────────────────────────

def cosine_oracle(
    pg: PgBridge,
    query_vec: list[float],
    *,
    project: Optional[str],
    oracle_pool: int,
) -> list[dict[str, Any]]:
    """
    Score every visible atom by raw cosine to query_vec — no weight, no recency.
    Returns the top `oracle_pool` rows (id, title, visit_count, last_visited,
    created_at, cosine) ordered by cosine descending. Visibility filters mirror
    hybrid_search defaults so an unretrievable atom is never called relevant.
    """
    vec_str = str(query_vec)
    filters = [
        "embedding IS NOT NULL",
        "invalid_at IS NULL",
        "NOT COALESCE((content->>'search_noise')::boolean, false)",
        "(tier IS NULL OR tier != 'superseded')",
    ]
    params: list = [vec_str]
    if project:
        filters.append("project = %s")
        params.append(project)
    where = " AND ".join(filters)
    params.append(oracle_pool)

    pg._ensure_conn()
    with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, title, visit_count, last_visited, created_at, valid_at,"
            " 1 - (embedding <=> %s::vector) AS cosine"
            f" FROM knowledge WHERE {where}"
            " ORDER BY embedding <=> %s::vector ASC LIMIT %s",
            [vec_str] + params[1:-1] + [vec_str, oracle_pool],
        )
        return [dict(r) for r in cur.fetchall()]


def _age_days(row: dict[str, Any], now: datetime) -> Optional[float]:
    ts = row.get("last_visited")
    if ts is None:
        return None
    if isinstance(ts, str):
        try:
            from dateutil import parser as _dp  # type: ignore
            ts = _dp.parse(ts)
        except Exception:
            return None
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max((now - ts).total_seconds() / 86400.0, 0.0)


def is_cold(row: dict[str, Any], now: datetime, *, cold_visit_max: int, cold_age_days: float) -> bool:
    """Low temperature: rarely visited AND (never visited OR not visited recently)."""
    vc = int(row.get("visit_count") or 0)
    if vc > cold_visit_max:
        return False
    age = _age_days(row, now)
    return age is None or age >= cold_age_days


def is_warm(row: dict[str, Any], now: datetime, *, cold_visit_max: int, cold_age_days: float) -> bool:
    return not is_cold(row, now, cold_visit_max=cold_visit_max, cold_age_days=cold_age_days)


def _recall_metrics(
    top_ids: list[str],
    *,
    k: int,
    cold_ids: set[str],
    warm_ids: set[str],
    relevant_ids: set[str],
) -> dict[str, Any]:
    top_set = set(top_ids[:k])
    cr_found = cold_ids & top_set
    wr_found = warm_ids & top_set
    rel_found = relevant_ids & top_set
    return {
        "cold_relevant_recall": (len(cr_found) / len(cold_ids)) if cold_ids else None,
        "warm_relevant_recall": (len(wr_found) / len(warm_ids)) if warm_ids else None,
        "relevant_recall": (len(rel_found) / len(relevant_ids)) if relevant_ids else None,
        "surfacing_precision": (len(rel_found) / k) if k else None,
        "cold_found": sorted(cr_found),
        "top_ids": top_ids[:k],
    }


# ── Per-query evaluation ───────────────────────────────────────────────────────

def evaluate_query(
    pg: PgBridge,
    query: dict[str, Any],
    *,
    k: int,
    oracle_n: int,
    oracle_pool: int,
    cosine_floor: float,
    cold_visit_max: int,
    cold_age_days: float,
    project: Optional[str],
    weight_modes: list[str],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    qtext = query["query"]
    qk = int(query.get("k", k))

    qvec = embed(qtext)
    if qvec is None:
        return {"id": query["id"], "query": qtext, "error": "embed_failed"}

    oracle = cosine_oracle(pg, qvec, project=project, oracle_pool=oracle_pool)
    relevant = [r for r in oracle[:oracle_n] if float(r["cosine"]) >= cosine_floor]
    cold_relevant = [
        r for r in relevant
        if is_cold(r, now, cold_visit_max=cold_visit_max, cold_age_days=cold_age_days)
    ]
    warm_relevant = [
        r for r in relevant
        if is_warm(r, now, cold_visit_max=cold_visit_max, cold_age_days=cold_age_days)
    ]
    cold_ids = {r["id"] for r in cold_relevant}
    warm_ids = {r["id"] for r in warm_relevant}
    relevant_ids = {r["id"] for r in relevant}

    by_mode: dict[str, dict[str, Any]] = {}
    for mode in weight_modes:
        use_weight = mode != "off"
        hits = hybrid_search(
            qtext, pg, limit=qk, project=project,
            weight_col=use_weight, weight_mode=mode if use_weight else "full",
        )
        by_mode[mode] = _recall_metrics(
            [h["id"] for h in hits],
            k=qk,
            cold_ids=cold_ids,
            warm_ids=warm_ids,
            relevant_ids=relevant_ids,
        )

    baseline = by_mode.get("full", {})
    best_mode = weight_modes[0]
    best_cr = baseline.get("cold_relevant_recall")
    lift_vs_full: Optional[float] = None
    if "full" in by_mode and len(weight_modes) > 1:
        for mode in weight_modes:
            if mode == "full":
                continue
            cr = by_mode[mode].get("cold_relevant_recall")
            if cr is not None and best_cr is not None and cr > best_cr:
                best_cr = cr
                best_mode = mode
        cr_full = by_mode["full"].get("cold_relevant_recall")
        cr_off = by_mode.get("off", {}).get("cold_relevant_recall")
        if cr_full is not None and cr_off is not None:
            lift_vs_full = cr_off - cr_full

    return {
        "id": query["id"],
        "query": qtext,
        "k": qk,
        "n_relevant": len(relevant),
        "n_cold_relevant": len(cold_relevant),
        "n_warm_relevant": len(warm_relevant),
        "cosine_top": round(float(oracle[0]["cosine"]), 4) if oracle else None,
        "modes": by_mode,
        "best_mode_by_cold_recall": best_mode,
        "cold_relevant_recall_lift_off_minus_full": (
            round(lift_vs_full, 4) if lift_vs_full is not None else None
        ),
    }


# ── Aggregation ────────────────────────────────────────────────────────────────

def _mean(values: list[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def aggregate(results: list[dict[str, Any]], weight_modes: list[str]) -> dict[str, Any]:
    scored = [r for r in results if "error" not in r and r["n_cold_relevant"] > 0]
    out: dict[str, Any] = {
        "queries_total": len(results),
        "queries_scored": len(scored),
        "queries_no_cold_relevant": sum(
            1 for r in results if "error" not in r and r["n_cold_relevant"] == 0
        ),
        "queries_embed_failed": sum(1 for r in results if r.get("error") == "embed_failed"),
        "by_mode": {},
    }
    for mode in weight_modes:
        cold = [r["modes"][mode]["cold_relevant_recall"] for r in scored if mode in r.get("modes", {})]
        warm = [r["modes"][mode]["warm_relevant_recall"] for r in scored if mode in r.get("modes", {})]
        rel = [r["modes"][mode]["relevant_recall"] for r in scored if mode in r.get("modes", {})]
        prec = [r["modes"][mode]["surfacing_precision"] for r in scored if mode in r.get("modes", {})]
        out["by_mode"][mode] = {
            "cold_relevant_recall": _mean(cold),
            "warm_relevant_recall": _mean(warm),
            "relevant_recall": _mean(rel),
            "surfacing_precision": _mean(prec),
        }
    if "full" in weight_modes and "off" in weight_modes:
        lifts = [
            (r["modes"]["off"]["cold_relevant_recall"] or 0)
            - (r["modes"]["full"]["cold_relevant_recall"] or 0)
            for r in scored
            if "off" in r.get("modes", {}) and "full" in r.get("modes", {})
        ]
        out["mean_lift_off_minus_full"] = _mean(lifts)
        out["queries_improved_off_vs_full"] = sum(1 for x in lifts if x > 0)
        out["queries_regressed_off_vs_full"] = sum(1 for x in lifts if x < 0)
    return out


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="WCE cold-relevant recall probe.")
    ap.add_argument("--queries", default=str(DEFAULT_QUERIES))
    ap.add_argument("--project", default=None, help="restrict to a single project (default: all)")
    ap.add_argument("--k", type=int, default=10, help="top-k retrieval cutoff")
    ap.add_argument("--oracle-n", type=int, default=20, help="relevant = top-N by cosine")
    ap.add_argument("--oracle-pool", type=int, default=300, help="atoms scored by the cosine oracle")
    ap.add_argument("--cosine-floor", type=float, default=0.5, help="min cosine to count as relevant")
    ap.add_argument("--cold-visit-max", type=int, default=1, help="visit_count <= this is cold")
    ap.add_argument("--cold-age-days", type=float, default=30.0, help="last_visited older than this is cold")
    ap.add_argument("--weight-mode", default="log", choices=WEIGHT_MODES,
                    help="single retrieval weight mode (default: log = live after fix)")
    ap.add_argument("--ablate", action="store_true",
                    help="run all weight modes and print comparison table")
    ap.add_argument("--no-write", action="store_true", help="skip writing the run JSON")
    args = ap.parse_args()

    weight_modes = list(WEIGHT_MODES) if args.ablate else [args.weight_mode]

    spec = json.loads(Path(args.queries).read_text(encoding="utf-8"))
    default_k = int(spec.get("default_k", args.k))
    queries = [q for q in spec.get("queries", []) if isinstance(q, dict) and q.get("query")]
    if not queries:
        print("No queries found.", file=sys.stderr)
        return 2

    config = {
        "k": args.k or default_k,
        "oracle_n": args.oracle_n,
        "oracle_pool": args.oracle_pool,
        "cosine_floor": args.cosine_floor,
        "cold_visit_max": args.cold_visit_max,
        "cold_age_days": args.cold_age_days,
        "project": args.project,
        "weight_modes": weight_modes,
    }

    results: list[dict[str, Any]] = []
    with PgBridge() as pg:
        eval_cfg = {k: v for k, v in config.items() if k != "weight_modes"}
        for q in queries:
            results.append(evaluate_query(pg, q, weight_modes=weight_modes, **eval_cfg))

    summary = aggregate(results, weight_modes)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "benchmark": "wce-cold-relevant-recall",
        "timestamp": timestamp,
        "config": config,
        "summary": summary,
        "results": results,
    }

    # ── Human-readable report ──
    print("\nWCE — cold-relevant recall probe")
    print(f"  config: k={config['k']} oracle_n={config['oracle_n']} "
          f"cosine_floor={config['cosine_floor']} "
          f"cold(visit<={config['cold_visit_max']}, age>={config['cold_age_days']}d)")
    if args.ablate:
        hdr = f"  {'mode':16} {'cold_rec':>9} {'warm_rec':>9} {'rel_rec':>9} {'precision':>9}"
        print(hdr)
        for mode in weight_modes:
            m = summary["by_mode"].get(mode, {})
            def f(x): return f"{x:.3f}" if isinstance(x, (int, float)) else "    -   "
            print(f"  {mode:16} {f(m.get('cold_relevant_recall')):>9} "
                  f"{f(m.get('warm_relevant_recall')):>9} {f(m.get('relevant_recall')):>9} "
                  f"{f(m.get('surfacing_precision')):>9}")
    else:
        mode = weight_modes[0]
        print(f"  mode={mode}")
        print(f"  {'query':28} {'n_cold':>6} {'cold':>6} {'warm':>6} {'prec':>6}")
        for r in results:
            if "error" in r:
                print(f"  {r['id'][:28]:28} {'ERR':>6} {r['error']}")
                continue
            m = r["modes"][mode]
            fmt = lambda x: f"{x:.2f}" if isinstance(x, (int, float)) else "  - "
            print(f"  {r['id'][:28]:28} {r['n_cold_relevant']:>6} "
                  f"{fmt(m['cold_relevant_recall']):>6} {fmt(m['warm_relevant_recall']):>6} "
                  f"{fmt(m['surfacing_precision']):>6}")

    print("\nAggregate:")
    for key, val in summary.items():
        if key == "by_mode":
            continue
        print(f"  {key:42} {val}")

    if not args.no_write:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        out = RUNS_DIR / f"wce_{timestamp}.json"
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
