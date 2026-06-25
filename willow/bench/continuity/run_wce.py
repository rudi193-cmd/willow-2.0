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
  python3 willow/bench/continuity/run_wce.py --tasks thread_recall,next_bite --agent willow
  python3 willow/bench/continuity/run_wce.py --tasks surfacing_precision,decision_persistence,staleness --agent willow
  python3 willow/bench/continuity/run_wce.py --tasks all --agent willow --ablate
  python3 willow/bench/continuity/run_wce.py --tasks cold_recall --cap-sweep 1.0,1.3,1.5,1.8,2.0

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
from dataclasses import dataclass
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
from willow.ranking.hybrid import (  # noqa: E402
    DEFAULT_COSINE_BYPASS,
    DEFAULT_WEIGHT_CAP,
    WEIGHT_MODES,
    hybrid_search,
)

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


# ── Weight-mode / cap-sweep variants ───────────────────────────────────────────

@dataclass(frozen=True)
class WeightVariant:
    label: str
    weight_mode: str = "log"
    weight_col: bool = True
    weight_cap: float = DEFAULT_WEIGHT_CAP
    cosine_bypass: float = DEFAULT_COSINE_BYPASS


def _parse_float_list(raw: str) -> list[float]:
    if not raw.strip():
        return []
    return [float(part.strip()) for part in raw.split(",") if part.strip()]


def build_weight_variants(
    *,
    ablate: bool,
    weight_mode: str,
    cap_sweep: list[float],
    weight_cap: float,
    cosine_bypass: float,
) -> list[WeightVariant]:
    """Build WCE retrieval variants. cap_sweep adds log/off baselines + cap@<value> rows."""
    if cap_sweep:
        variants = [
            WeightVariant("log", weight_mode="log", weight_cap=weight_cap, cosine_bypass=cosine_bypass),
            WeightVariant("off", weight_mode="full", weight_col=False),
        ]
        for cap in cap_sweep:
            variants.append(
                WeightVariant(
                    f"cap@{cap:g}",
                    weight_mode="cap",
                    weight_cap=cap,
                    cosine_bypass=cosine_bypass,
                )
            )
        if ablate:
            variants = [
                WeightVariant("full", weight_mode="full", weight_cap=weight_cap, cosine_bypass=cosine_bypass),
                *variants,
                WeightVariant(
                    "cosine_bypass",
                    weight_mode="cosine_bypass",
                    weight_cap=weight_cap,
                    cosine_bypass=cosine_bypass,
                ),
            ]
        return variants
    if ablate:
        return [
            WeightVariant(
                mode,
                weight_mode=mode,
                weight_col=(mode != "off"),
                weight_cap=weight_cap,
                cosine_bypass=cosine_bypass,
            )
            for mode in WEIGHT_MODES
        ]
    return [
        WeightVariant(
            weight_mode,
            weight_mode=weight_mode,
            weight_cap=weight_cap,
            cosine_bypass=cosine_bypass,
        )
    ]


def pick_knee_cap(
    by_mode: dict[str, dict[str, Any]],
    *,
    baseline: str = "log",
    min_warm: Optional[float] = None,
    warm_tolerance: float = 0.035,
) -> dict[str, Any]:
    """Best cap@ value: max cold recall among cap sweeps that keep warm near baseline."""
    base = by_mode.get(baseline) or {}
    base_warm = base.get("warm_relevant_recall")
    floor = min_warm
    if floor is None and base_warm is not None:
        floor = float(base_warm) - warm_tolerance
    candidates: list[tuple[float, float, float, str]] = []
    for label, metrics in by_mode.items():
        if not label.startswith("cap@"):
            continue
        cold = metrics.get("cold_relevant_recall")
        warm = metrics.get("warm_relevant_recall")
        if cold is None or warm is None:
            continue
        if floor is not None and float(warm) < floor:
            continue
        try:
            cap_val = float(label.split("@", 1)[1])
        except (IndexError, ValueError):
            continue
        candidates.append((float(cold), float(warm), cap_val, label))
    if not candidates:
        return {"knee": None, "reason": "no_cap_variant_meets_warm_floor", "warm_floor": floor}
    candidates.sort(key=lambda row: (-row[0], -row[1]))
    best = candidates[0]
    return {
        "knee": best[3],
        "weight_cap": best[2],
        "cold_relevant_recall": round(best[0], 4),
        "warm_relevant_recall": round(best[1], 4),
        "baseline": baseline,
        "warm_floor": floor,
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
    weight_variants: list[WeightVariant],
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
    for var in weight_variants:
        hits = hybrid_search(
            qtext, pg, limit=qk, project=project,
            weight_col=var.weight_col,
            weight_mode=var.weight_mode if var.weight_col else "full",
            weight_cap=var.weight_cap,
            cosine_bypass=var.cosine_bypass,
        )
        by_mode[var.label] = _recall_metrics(
            [h["id"] for h in hits],
            k=qk,
            cold_ids=cold_ids,
            warm_ids=warm_ids,
            relevant_ids=relevant_ids,
        )

    labels = [v.label for v in weight_variants]
    baseline_label = "full" if "full" in by_mode else labels[0]
    baseline = by_mode.get(baseline_label, {})
    best_mode = labels[0]
    best_cr = baseline.get("cold_relevant_recall")
    lift_vs_full: Optional[float] = None
    if "full" in by_mode and "off" in by_mode:
        cr_full = by_mode["full"].get("cold_relevant_recall")
        cr_off = by_mode["off"].get("cold_relevant_recall")
        if cr_full is not None and cr_off is not None:
            lift_vs_full = cr_off - cr_full
    if len(labels) > 1:
        for label in labels:
            if label == baseline_label:
                continue
            cr = by_mode[label].get("cold_relevant_recall")
            if cr is not None and best_cr is not None and cr > best_cr:
                best_cr = cr
                best_mode = label

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


def _fmt_score(x: object, *, decimals: int = 2) -> str:
    if isinstance(x, (int, float)):
        return f"{x:.{decimals}f}"
    return "  - " if decimals == 2 else "    -   "


def aggregate(results: list[dict[str, Any]], variant_labels: list[str]) -> dict[str, Any]:
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
    for label in variant_labels:
        cold = [r["modes"][label]["cold_relevant_recall"] for r in scored if label in r.get("modes", {})]
        warm = [r["modes"][label]["warm_relevant_recall"] for r in scored if label in r.get("modes", {})]
        rel = [r["modes"][label]["relevant_recall"] for r in scored if label in r.get("modes", {})]
        prec = [r["modes"][label]["surfacing_precision"] for r in scored if label in r.get("modes", {})]
        out["by_mode"][label] = {
            "cold_relevant_recall": _mean(cold),
            "warm_relevant_recall": _mean(warm),
            "relevant_recall": _mean(rel),
            "surfacing_precision": _mean(prec),
        }
    if "full" in variant_labels and "off" in variant_labels:
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

WCE_TASKS = (
    "cold_recall",
    "thread_recall",
    "next_bite",
    "surfacing_precision",
    "decision_persistence",
    "staleness",
    "all",
)


def _parse_tasks(raw: str) -> list[str]:
    tasks = [t.strip() for t in raw.split(",") if t.strip()]
    if not tasks:
        return ["cold_recall"]
    if "all" in tasks:
        return [
            "cold_recall",
            "thread_recall",
            "next_bite",
            "surfacing_precision",
            "decision_persistence",
            "staleness",
        ]
    unknown = [t for t in tasks if t not in WCE_TASKS]
    if unknown:
        raise SystemExit(f"Unknown task(s): {unknown}. Valid: {', '.join(WCE_TASKS)}")
    return tasks


def _run_handoff_report(
    agent: str,
    tasks: list[str],
    pair_limit: int,
    *,
    max_threads: int = 5,
    max_atoms: int = 3,
) -> dict[str, Any]:
    from willow.bench.continuity.handoff_eval import run_handoff_tasks

    handoff_tasks = [
        t for t in tasks
        if t in (
            "thread_recall",
            "next_bite",
            "surfacing_precision",
            "decision_persistence",
            "staleness",
        )
    ]
    pg = None
    if any(t in handoff_tasks for t in ("surfacing_precision", "staleness")):
        pg = PgBridge()
        pg.__enter__()
    try:
        payload = run_handoff_tasks(
            agent,
            tasks=handoff_tasks,
            pair_limit=pair_limit,
            pg=pg,
            max_threads=max_threads,
            max_atoms=max_atoms,
        )
    finally:
        if pg is not None:
            pg.__exit__(None, None, None)
    summary = payload["summary"]

    print("\nWCE — handoff continuity (session pairs N → N+1)")
    print(f"  agent={agent}  handoffs={summary['handoffs_loaded']}  pairs={summary['pairs_evaluated']}")
    if "thread_recall" in handoff_tasks:
        print(f"  {'pair':52} {'recall':>7} {'n_thr':>5}")
        for row in payload["pairs"]:
            tr = row.get("thread_recall") or {}
            if tr.get("recall") is None:
                continue
            pair = row["pair"]
            if len(pair) > 52:
                pair = "…" + pair[-51:]
            print(f"  {pair:52} {tr['recall']:>7.2f} {tr.get('n_threads', 0):>5}")
        print(f"  thread_recall_mean: {summary.get('thread_recall_mean')}")
    if "next_bite" in handoff_tasks:
        print(f"\n  {'pair':52} {'hit':>5}")
        for row in payload["pairs"]:
            nb = row.get("next_bite") or {}
            if nb.get("hit") is None:
                continue
            pair = row["pair"]
            if len(pair) > 52:
                pair = "…" + pair[-51:]
            print(f"  {pair:52} {'yes' if nb['hit'] else 'no':>5}")
        print(f"  next_bite_hit_rate: {summary.get('next_bite_hit_rate')}")
    if "surfacing_precision" in handoff_tasks:
        print(f"\n  {'pair':52} {'prec':>7} {'surf':>5} {'used':>5}")
        for row in payload["pairs"]:
            sp = row.get("surfacing_precision") or {}
            if sp.get("precision") is None:
                continue
            pair = row["pair"]
            if len(pair) > 52:
                pair = "…" + pair[-51:]
            print(f"  {pair:52} {sp['precision']:>7.2f} {sp.get('n_surfaced', 0):>5} {sp.get('n_used', 0):>5}")
        print(f"  surfacing_precision_mean: {summary.get('surfacing_precision_mean')}")
    if "decision_persistence" in handoff_tasks:
        print(f"\n  {'pair':52} {'re-lit':>7} {'n_agr':>5}")
        for row in payload["pairs"]:
            dp = row.get("decision_persistence") or {}
            if dp.get("relitigation_rate") is None:
                continue
            pair = row["pair"]
            if len(pair) > 52:
                pair = "…" + pair[-51:]
            print(f"  {pair:52} {dp['relitigation_rate']:>7.2f} {dp.get('n_agreements', 0):>5}")
        print(f"  relitigation_rate_mean: {summary.get('relitigation_rate_mean')}")
    if "staleness" in handoff_tasks:
        print(f"\n  {'pair':52} {'flag':>7} {'acted':>7} {'n_ss':>5}")
        for row in payload["pairs"]:
            st = row.get("staleness") or {}
            if st.get("stale_flag_rate") is None and st.get("n_superseded", 0) == 0:
                continue
            pair = row["pair"]
            if len(pair) > 52:
                pair = "…" + pair[-51:]
            flag = st.get("stale_flag_rate")
            acted = st.get("acted_on_stale_rate")
            flag_s = f"{flag:.2f}" if isinstance(flag, (int, float)) else "  -"
            acted_s = f"{acted:.2f}" if isinstance(acted, (int, float)) else "  -"
            print(f"  {pair:52} {flag_s:>7} {acted_s:>7} {st.get('n_superseded', 0):>5}")
        print(f"  stale_flag_rate_mean: {summary.get('stale_flag_rate_mean')}")
        print(f"  acted_on_stale_rate_mean: {summary.get('acted_on_stale_rate_mean')}")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Willow Continuity Eval (WCE).")
    ap.add_argument("--tasks", default="cold_recall",
                    help="comma-separated: cold_recall, thread_recall, next_bite, "
                         "surfacing_precision, decision_persistence, staleness, all")
    ap.add_argument("--agent", default="willow", help="agent id for handoff tasks")
    ap.add_argument("--pair-limit", type=int, default=0,
                    help="max consecutive handoff pairs to score (0 = all)")
    ap.add_argument("--boot-max-threads", type=int, default=5,
                    help="surfacing_precision: max open threads counted as boot clutter")
    ap.add_argument("--boot-max-atoms", type=int, default=3,
                    help="surfacing_precision: max atom IDs counted as boot clutter")
    ap.add_argument("--queries", default=str(DEFAULT_QUERIES))
    ap.add_argument("--project", default=None, help="restrict to a single project (default: all)")
    ap.add_argument("--k", type=int, default=10, help="top-k retrieval cutoff")
    ap.add_argument("--oracle-n", type=int, default=20, help="relevant = top-N by cosine")
    ap.add_argument("--oracle-pool", type=int, default=300, help="atoms scored by the cosine oracle")
    ap.add_argument("--cosine-floor", type=float, default=0.5, help="min cosine to count as relevant")
    ap.add_argument("--cold-visit-max", type=int, default=1, help="visit_count <= this is cold")
    ap.add_argument("--cold-age-days", type=float, default=30.0, help="last_visited older than this is cold")
    ap.add_argument("--weight-mode", default="cap", choices=WEIGHT_MODES,
                    help="single retrieval weight mode (default: cap = live WCE knee)")
    ap.add_argument("--weight-cap", type=float, default=DEFAULT_WEIGHT_CAP,
                    help="weight_cap for cap/cosine_bypass modes (default: hybrid DEFAULT_WEIGHT_CAP)")
    ap.add_argument("--cosine-bypass", type=float, default=DEFAULT_COSINE_BYPASS,
                    help="cosine floor for cosine_bypass mode")
    ap.add_argument("--cap-sweep", default="",
                    help="comma-separated cap values — runs log+off baselines and cap@<v> each")
    ap.add_argument("--ablate", action="store_true",
                    help="run all weight modes (or add full+cosine_bypass when --cap-sweep set)")
    ap.add_argument("--min-warm", type=float, default=None,
                    help="knee picker: minimum warm recall (default: log warm - 0.035)")
    ap.add_argument("--no-write", action="store_true", help="skip writing the run JSON")
    ap.add_argument("--output", default="", help="write JSON to this path (default: runs/wce_<timestamp>.json)")
    args = ap.parse_args()

    try:
        task_list = _parse_tasks(args.tasks)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload: dict[str, Any] = {
        "benchmark": "wce",
        "timestamp": timestamp,
        "tasks": task_list,
        "agent": args.agent,
    }

    if any(
        t in task_list
        for t in (
            "thread_recall",
            "next_bite",
            "surfacing_precision",
            "decision_persistence",
            "staleness",
        )
    ):
        payload["handoff"] = _run_handoff_report(
            args.agent,
            task_list,
            args.pair_limit,
            max_threads=args.boot_max_threads,
            max_atoms=args.boot_max_atoms,
        )

    if "cold_recall" not in task_list:
        if not args.no_write:
            RUNS_DIR.mkdir(parents=True, exist_ok=True)
            out = Path(args.output) if args.output else RUNS_DIR / f"wce_{timestamp}.json"
            out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            print(f"\nWrote {out}")
        return 0

    cap_sweep = _parse_float_list(args.cap_sweep)
    if cap_sweep and not args.ablate and args.weight_mode != "log":
        print("Note: --cap-sweep uses log as baseline; --weight-mode ignored.", file=sys.stderr)
    weight_variants = build_weight_variants(
        ablate=args.ablate,
        weight_mode=args.weight_mode,
        cap_sweep=cap_sweep,
        weight_cap=args.weight_cap,
        cosine_bypass=args.cosine_bypass,
    )
    variant_labels = [v.label for v in weight_variants]

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
        "weight_cap": args.weight_cap,
        "cosine_bypass": args.cosine_bypass,
        "cap_sweep": cap_sweep,
        "variant_labels": variant_labels,
    }

    results: list[dict[str, Any]] = []
    with PgBridge() as pg:
        eval_cfg = {
            k: v for k, v in config.items()
            if k not in ("variant_labels", "cap_sweep", "weight_cap", "cosine_bypass")
        }
        for q in queries:
            results.append(evaluate_query(pg, q, weight_variants=weight_variants, **eval_cfg))

    summary = aggregate(results, variant_labels)
    knee = pick_knee_cap(summary["by_mode"], baseline="log", min_warm=args.min_warm) if cap_sweep else {}
    payload["cold_recall"] = {
        "config": config,
        "summary": summary,
        "knee": knee,
        "results": results,
    }

    # ── Human-readable report ──
    print("\nWCE — cold-relevant recall probe")
    print(f"  config: k={config['k']} oracle_n={config['oracle_n']} "
          f"cosine_floor={config['cosine_floor']} "
          f"cold(visit<={config['cold_visit_max']}, age>={config['cold_age_days']}d)")
    multi_variant = len(variant_labels) > 1
    if multi_variant:
        col_w = max(16, max(len(lbl) for lbl in variant_labels) + 1)
        hdr = f"  {'mode':<{col_w}} {'cold_rec':>9} {'warm_rec':>9} {'rel_rec':>9} {'precision':>9}"
        print(hdr)
        for label in variant_labels:
            m = summary["by_mode"].get(label, {})
            print(f"  {label:<{col_w}} {_fmt_score(m.get('cold_relevant_recall'), decimals=3):>9} "
                  f"{_fmt_score(m.get('warm_relevant_recall'), decimals=3):>9} "
                  f"{_fmt_score(m.get('relevant_recall'), decimals=3):>9} "
                  f"{_fmt_score(m.get('surfacing_precision'), decimals=3):>9}")
        if knee.get("knee"):
            print(
                f"\n  knee: {knee['knee']}  cold={knee['cold_relevant_recall']}  "
                f"warm={knee['warm_relevant_recall']}  (floor warm>={knee.get('warm_floor')})"
            )
        elif cap_sweep and knee.get("reason"):
            print(f"\n  knee: none ({knee['reason']})", file=sys.stderr)
    else:
        label = variant_labels[0]
        print(f"  mode={label}")
        print(f"  {'query':28} {'n_cold':>6} {'cold':>6} {'warm':>6} {'prec':>6}")
        for r in results:
            if "error" in r:
                print(f"  {r['id'][:28]:28} {'ERR':>6} {r['error']}")
                continue
            m = r["modes"][label]
            print(f"  {r['id'][:28]:28} {r['n_cold_relevant']:>6} "
                  f"{_fmt_score(m['cold_relevant_recall']):>6} "
                  f"{_fmt_score(m['warm_relevant_recall']):>6} "
                  f"{_fmt_score(m['surfacing_precision']):>6}")

    print("\nAggregate:")
    for key, val in summary.items():
        if key == "by_mode":
            continue
        print(f"  {key:42} {val}")

    if not args.no_write:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        out = Path(args.output) if args.output else RUNS_DIR / f"wce_{timestamp}.json"
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
