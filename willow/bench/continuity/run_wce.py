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
from willow.ranking.continuity_pool import (  # noqa: E402
    CONTINUITY_GRADE_DENY_SOURCE_TYPES,
    CONTINUITY_GRADE_DENY_TITLE_PREFIXES,
    resolve_continuity_source_types,
)

import psycopg2.extras  # noqa: E402


# ── Oracle: recency-blind cosine relevance ────────────────────────────────────

def cosine_oracle(
    pg: PgBridge,
    query_vec: list[float],
    *,
    project: Optional[str],
    oracle_pool: int,
    source_types: Optional[list[str]] = None,
    continuity_grade: bool = False,
) -> list[dict[str, Any]]:
    """
    Score every visible atom by raw cosine to query_vec — no weight, no recency.
    Returns the top `oracle_pool` rows (id, title, source_type, visit_count,
    last_visited, created_at, cosine) ordered by cosine descending. Visibility
    filters mirror hybrid_search defaults so an unretrievable atom is never
    called relevant.

    `source_types`, when set, restricts the oracle corpus to those source_types —
    the memory-layer ablation uses it to define the relevant set over the
    non-LoCoMo "full stack" (B3*) rather than the whole contaminated table.

    `continuity_grade` (WCE eval-validity, KB D9922FEF) applies a continuity-grade
    DENY-list on top of any allow-list: it drops low-continuity source_types
    (revelation/dark_matter/intake) and dirty/pipe/revelation title prefixes so
    the cold/warm axis is non-degenerate (~62/38 split, not ~83% all-cold). This
    composes with `source_types` (allow-list AND deny-list).
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
    if source_types:
        filters.append("source_type = ANY(%s)")
        params.append(list(source_types))
    if continuity_grade:
        # Deny low-continuity source_types (COALESCE so a NULL type — not on the
        # deny-list — is kept, not silently dropped).
        filters.append("COALESCE(source_type, '') <> ALL(%s)")
        params.append(list(CONTINUITY_GRADE_DENY_SOURCE_TYPES))
        # Deny dirty/pipe/revelation title prefixes. '[' is literal in LIKE.
        for prefix in CONTINUITY_GRADE_DENY_TITLE_PREFIXES:
            filters.append("COALESCE(title, '') NOT LIKE %s")
            params.append(prefix + "%")
    where = " AND ".join(filters)
    params.append(oracle_pool)

    pg._ensure_conn()
    with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, title, source_type, visit_count, last_visited, created_at, valid_at,"
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


# ── Memory-layer ablation (B0–B3): attribute cold recall to memory layers ──────
#
# Cumulative source_type allow-lists over the knowledge table. Each layer adds
# sources to the one before it, so the marginal cold-recall lift B(i-1)→B(i)
# attributes recall to the layer that was added. The relevant/cold set is fixed
# once over the full non-LoCoMo stack (B3*), then the live ranker's retrieval
# pool is restricted per layer — same target atoms, widening haystack.
#
# B3 "full stack" is every embedded source_type EXCEPT the benchmark/LoCoMo eval
# atoms that dominate and contaminate the knowledge table (operator decision
# 2026-06-25: "knowledge minus LoCoMo").

LAYER_HANDOFF = ["session", "session_promote", "hook_stop", "handoff"]
LAYER_KB_ADD = [
    "mcp", "revelation", "intake", "seed", "dark_matter",
    "agent-synthesis", "community_detection", "mycorrhizal",
    "norn_pass", "drift-resolve", "nest-seed", "discovered_pattern", "think_map",
]
LAYER_EXTERNAL_ADD = [
    "external", "fetched", "literature", "web_search",
    "ai_news", "repo_doc", "public-demo",
]
# Excluded from B3 "full stack" — LoCoMo / benchmark eval contamination.
LAYER_EXCLUDE_FROM_FULL = {"benchmark"}


def _all_embedded_source_types(pg: PgBridge, *, exclude: set[str]) -> list[str]:
    """Distinct source_types with at least one embedded, valid atom, minus `exclude`."""
    pg._ensure_conn()
    with pg.conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT source_type FROM knowledge"
            " WHERE embedding IS NOT NULL AND invalid_at IS NULL"
            " AND source_type IS NOT NULL"
        )
        return sorted(r[0] for r in cur.fetchall() if r[0] not in exclude)


def build_memory_layers(pg: PgBridge) -> list[tuple[str, list[str]]]:
    """Cumulative (label, source_types) layers B0→B3 for the ablation."""
    handoff = list(dict.fromkeys(LAYER_HANDOFF))
    kb = list(dict.fromkeys(handoff + LAYER_KB_ADD))
    external = list(dict.fromkeys(kb + LAYER_EXTERNAL_ADD))
    full = list(dict.fromkeys(external + _all_embedded_source_types(pg, exclude=LAYER_EXCLUDE_FROM_FULL)))
    return [
        ("B0_handoff", handoff),
        ("B1_kb", kb),
        ("B2_external", external),
        ("B3_full", full),
    ]


def evaluate_query_layers(
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
    layers: list[tuple[str, list[str]]],
    oracle_source_types: list[str],
) -> dict[str, Any]:
    """Cold-relevant recall per memory layer for one query (fixed oracle, live cap ranker)."""
    now = datetime.now(timezone.utc)
    qtext = query["query"]
    qk = int(query.get("k", k))

    qvec = embed(qtext)
    if qvec is None:
        return {"id": query["id"], "query": qtext, "error": "embed_failed"}

    oracle = cosine_oracle(
        pg, qvec, project=project, oracle_pool=oracle_pool,
        source_types=oracle_source_types,
    )
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

    # Attribute the cold-relevant target atoms to the layer they live in.
    cold_by_source: dict[str, int] = {}
    for r in cold_relevant:
        st = r.get("source_type") or "(null)"
        cold_by_source[st] = cold_by_source.get(st, 0) + 1

    by_layer: dict[str, dict[str, Any]] = {}
    for label, stypes in layers:
        hits = hybrid_search(qtext, pg, limit=qk, project=project, source_types=stypes)
        by_layer[label] = _recall_metrics(
            [h["id"] for h in hits],
            k=qk,
            cold_ids=cold_ids,
            warm_ids=warm_ids,
            relevant_ids=relevant_ids,
        )

    return {
        "id": query["id"],
        "query": qtext,
        "k": qk,
        "n_relevant": len(relevant),
        "n_cold_relevant": len(cold_relevant),
        "n_warm_relevant": len(warm_relevant),
        "cosine_top": round(float(oracle[0]["cosine"]), 4) if oracle else None,
        "cold_by_source": cold_by_source,
        "layers": by_layer,
    }


def aggregate_layers(results: list[dict[str, Any]], layer_labels: list[str]) -> dict[str, Any]:
    """Mean cold/warm/relevant recall per layer + marginal cold lift + cold source mix."""
    scored = [r for r in results if "error" not in r and r["n_cold_relevant"] > 0]
    out: dict[str, Any] = {
        "queries_total": len(results),
        "queries_scored": len(scored),
        "queries_no_cold_relevant": sum(
            1 for r in results if "error" not in r and r["n_cold_relevant"] == 0
        ),
        "queries_embed_failed": sum(1 for r in results if r.get("error") == "embed_failed"),
        "by_layer": {},
    }
    for label in layer_labels:
        cold = [r["layers"][label]["cold_relevant_recall"] for r in scored if label in r.get("layers", {})]
        warm = [r["layers"][label]["warm_relevant_recall"] for r in scored if label in r.get("layers", {})]
        rel = [r["layers"][label]["relevant_recall"] for r in scored if label in r.get("layers", {})]
        out["by_layer"][label] = {
            "cold_relevant_recall": _mean(cold),
            "warm_relevant_recall": _mean(warm),
            "relevant_recall": _mean(rel),
        }
    marginal: dict[str, Optional[float]] = {}
    prev: Optional[float] = None
    prev_label: Optional[str] = None
    for label in layer_labels:
        cur = out["by_layer"][label]["cold_relevant_recall"]
        if prev is not None and cur is not None:
            marginal[f"{prev_label}->{label}"] = round(cur - prev, 4)
        prev = cur
        prev_label = label
    out["marginal_cold_lift"] = marginal
    dist: dict[str, int] = {}
    for r in scored:
        for st, n in (r.get("cold_by_source") or {}).items():
            dist[st] = dist.get(st, 0) + n
    out["cold_source_distribution"] = dict(sorted(dist.items(), key=lambda kv: -kv[1]))
    return out


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
    source_types: Optional[list[str]] = None,
    continuity_grade: bool = False,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    qtext = query["query"]
    qk = int(query.get("k", k))

    qvec = embed(qtext)
    if qvec is None:
        return {"id": query["id"], "query": qtext, "error": "embed_failed"}

    oracle = cosine_oracle(
        pg, qvec, project=project, oracle_pool=oracle_pool,
        continuity_grade=continuity_grade,
    )
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
            source_types=source_types,
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


# ── Promotion-policy replay (Lever B1) ─────────────────────────────────────────
#
# The retrieval-side weight multiplier is already tamed (cap@1.4, PR #512). This
# probe attacks the *promotion* side. sap_mcp promotes knowledge[:3] of EVERY
# search (core/pg_bridge.py promote(): visit_count++, last_visited=now,
# weight = 1 + ln(1+vc)*rf). Aggravator (a) of KB 270F089E: a search returns
# top-k but only the top-3 ever warm, so a rank-4..k cold-but-relevant atom never
# promotes and then slides under norn's demote_stale. That is a DYNAMIC feedback
# effect the static cold_recall probe cannot see — it runs hybrid_search once
# against a frozen weight snapshot.
#
# Method: hold the oracle/relevant/cold sets FIXED (recency-blind, computed before
# any replay), then for each promotion policy replay the query stream `rounds`
# times — running the live retrieval config (cap@weight_cap, curated pool) and
# applying that policy's promotion to each result — then measure cold-relevant
# recall@k on the resulting weights. The whole replay runs inside ONE transaction
# that we ROLL BACK, so live weights are never mutated. hybrid_search is pure
# retrieval (the top-3 promotion lives in sap_mcp, not the ranker), so the only
# weight changes during a replay are the policy promotions we apply explicitly.

PROMOTION_POLICIES = ("none", "top1", "top3", "top5", "top10", "relgate")
# none    — control: no promotion at all (frozen weights baseline)
# topN    — promote the first N retrieved hits each search (top3 = live baseline)
# relgate — promote any hit with _cosine_sim >= relgate_floor (relevance-gated,
#           unbounded N): warm only what is genuinely on-topic, regardless of rank

_TOPN_POLICY = {"top1": 1, "top3": 3, "top5": 5, "top10": 10}

# Same weight recompute as core/pg_bridge.py promote(), but WITHOUT the commit —
# the update lives in the replay transaction and is discarded on rollback.
_REPLAY_PROMOTE_SQL = """
    WITH base AS (
        SELECT
            visit_count + 1 AS new_vc,
            CASE
                WHEN COALESCE(last_visited, now()) >= now() - INTERVAL '7 days'
                THEN 1.0
                ELSE GREATEST(0.1,
                    1.0 - (0.9 / 173.0) *
                    LEAST(173, EXTRACT(EPOCH FROM (now() - last_visited)) / 86400.0 - 7)
                )
            END AS rf
        FROM knowledge WHERE id = %s
    )
    UPDATE knowledge
    SET visit_count  = base.new_vc,
        last_visited = now(),
        weight       = 1.0 + ln(1.0 + base.new_vc) * base.rf
    FROM base
    WHERE knowledge.id = %s
"""


def _replay_promote(pg: PgBridge, atom_id: str) -> None:
    """Apply one promote() to atom_id on the shared connection WITHOUT committing."""
    with pg.conn.cursor() as cur:
        cur.execute(_REPLAY_PROMOTE_SQL, (atom_id, atom_id))


def _hits_to_promote(hits: list[dict], policy: str, *, relgate_floor: float) -> list[str]:
    """Which retrieved atom ids this policy would promote for one search."""
    if policy == "none":
        return []
    if policy == "relgate":
        out = []
        for h in hits:
            cos = h.get("_cosine_sim")
            if cos is not None and float(cos) >= relgate_floor and h.get("id"):
                out.append(h["id"])
        return out
    n = _TOPN_POLICY.get(policy)
    if n is None:
        raise ValueError(f"unknown promotion policy: {policy!r}; expected {PROMOTION_POLICIES}")
    return [h["id"] for h in hits[:n] if h.get("id")]


def _fixed_oracle_sets(
    pg: PgBridge,
    queries: list[dict[str, Any]],
    *,
    k: int,
    oracle_n: int,
    oracle_pool: int,
    cosine_floor: float,
    cold_visit_max: int,
    cold_age_days: float,
    project: Optional[str],
    oracle_source_types: Optional[list[str]],
    continuity_grade: bool = False,
) -> list[dict[str, Any]]:
    """Per-query relevant/cold/warm id sets, recency-blind, computed ONCE pre-replay."""
    now = datetime.now(timezone.utc)
    fixed: list[dict[str, Any]] = []
    for q in queries:
        qtext = q["query"]
        qk = int(q.get("k", k))
        qvec = embed(qtext)
        if qvec is None:
            fixed.append({"id": q["id"], "query": qtext, "k": qk, "error": "embed_failed"})
            continue
        oracle = cosine_oracle(
            pg, qvec, project=project, oracle_pool=oracle_pool,
            source_types=oracle_source_types,
            continuity_grade=continuity_grade,
        )
        relevant = [r for r in oracle[:oracle_n] if float(r["cosine"]) >= cosine_floor]
        cold_ids = {
            r["id"] for r in relevant
            if is_cold(r, now, cold_visit_max=cold_visit_max, cold_age_days=cold_age_days)
        }
        warm_ids = {
            r["id"] for r in relevant
            if is_warm(r, now, cold_visit_max=cold_visit_max, cold_age_days=cold_age_days)
        }
        fixed.append({
            "id": q["id"], "query": qtext, "k": qk,
            "cold_ids": cold_ids, "warm_ids": warm_ids,
            "relevant_ids": {r["id"] for r in relevant},
            "n_cold_relevant": len(cold_ids),
            "n_warm_relevant": len(warm_ids),
            "n_relevant": len(relevant),
        })
    return fixed


def run_promotion_replay(
    pg: PgBridge,
    fixed: list[dict[str, Any]],
    *,
    policies: list[str],
    rounds: int,
    project: Optional[str],
    retrieval_source_types: Optional[list[str]],
    weight_cap: float,
    cosine_bypass: float,
    relgate_floor: float,
) -> dict[str, Any]:
    """For each policy: snapshot → replay promotions `rounds`× → measure → rollback."""

    def _search(fq: dict[str, Any]) -> list[dict]:
        # Live retrieval config: cap multiplier + curated pool (promotion is the
        # only variable under test, so retrieval is held at the live default).
        return hybrid_search(
            fq["query"], pg, limit=fq["k"], project=project,
            weight_col=True, weight_mode="cap",
            weight_cap=weight_cap, cosine_bypass=cosine_bypass,
            source_types=retrieval_source_types,
        )

    scorable = [fq for fq in fixed if "error" not in fq]
    by_policy: dict[str, Any] = {}
    for policy in policies:
        try:
            # Replay: warm the snapshot under this policy.
            for _ in range(rounds):
                for fq in scorable:
                    for aid in _hits_to_promote(_search(fq), policy, relgate_floor=relgate_floor):
                        _replay_promote(pg, aid)
            # Measure on the warmed snapshot.
            per_query: list[dict[str, Any]] = []
            for fq in scorable:
                hits = _search(fq)
                metrics = _recall_metrics(
                    [h["id"] for h in hits], k=fq["k"],
                    cold_ids=fq["cold_ids"], warm_ids=fq["warm_ids"],
                    relevant_ids=fq["relevant_ids"],
                )
                per_query.append({
                    "id": fq["id"],
                    "n_cold_relevant": fq["n_cold_relevant"],
                    "n_warm_relevant": fq["n_warm_relevant"],
                    "metrics": metrics,
                })
        finally:
            # Discard EVERY promotion this policy applied — live weights untouched.
            pg.conn.rollback()

        scored = [r for r in per_query if r["n_cold_relevant"] > 0]
        by_policy[policy] = {
            "queries_scored": len(scored),
            "cold_relevant_recall": _mean([r["metrics"]["cold_relevant_recall"] for r in scored]),
            "warm_relevant_recall": _mean([r["metrics"]["warm_relevant_recall"] for r in scored]),
            "relevant_recall": _mean([r["metrics"]["relevant_recall"] for r in scored]),
            "surfacing_precision": _mean([r["metrics"]["surfacing_precision"] for r in scored]),
            "per_query": per_query,
        }

    baseline = by_policy.get("top3", {})
    base_cold = baseline.get("cold_relevant_recall")
    base_warm = baseline.get("warm_relevant_recall")
    deltas: dict[str, Any] = {}
    for policy, m in by_policy.items():
        if policy == "top3":
            continue
        c, w = m.get("cold_relevant_recall"), m.get("warm_relevant_recall")
        deltas[policy] = {
            "cold_vs_top3": round(c - base_cold, 4) if c is not None and base_cold is not None else None,
            "warm_vs_top3": round(w - base_warm, 4) if w is not None and base_warm is not None else None,
        }
    return {
        "rounds": rounds,
        "policies": policies,
        "relgate_floor": relgate_floor,
        "queries_total": len(fixed),
        "queries_embed_failed": sum(1 for fq in fixed if fq.get("error") == "embed_failed"),
        "by_policy": by_policy,
        "vs_top3_baseline": deltas,
    }


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


def _run_layer_ablation(
    args: argparse.Namespace,
    queries: list[dict[str, Any]],
    default_k: int,
    payload: dict[str, Any],
    timestamp: str,
) -> int:
    """Memory-layer ablation B0-B3: where does cold-relevant recall come from?"""
    k = args.k or default_k
    results: list[dict[str, Any]] = []
    with PgBridge() as pg:
        layers = build_memory_layers(pg)
        layer_labels = [label for label, _ in layers]
        oracle_source_types = layers[-1][1]  # B3 full non-LoCoMo stack
        for q in queries:
            results.append(
                evaluate_query_layers(
                    pg, q,
                    k=k,
                    oracle_n=args.oracle_n,
                    oracle_pool=args.oracle_pool,
                    cosine_floor=args.cosine_floor,
                    cold_visit_max=args.cold_visit_max,
                    cold_age_days=args.cold_age_days,
                    project=args.project,
                    layers=layers,
                    oracle_source_types=oracle_source_types,
                )
            )

    summary = aggregate_layers(results, layer_labels)
    config = {
        "k": k,
        "oracle_n": args.oracle_n,
        "oracle_pool": args.oracle_pool,
        "cosine_floor": args.cosine_floor,
        "cold_visit_max": args.cold_visit_max,
        "cold_age_days": args.cold_age_days,
        "project": args.project,
        "layer_labels": layer_labels,
        "layer_source_types": {label: stypes for label, stypes in layers},
    }
    payload["layer_ablation"] = {
        "config": config,
        "summary": summary,
        "results": results,
    }

    # ── Human-readable report ──
    print("\nWCE — memory-layer ablation (B0-B3, live cap ranker)")
    print(f"  config: k={k} oracle_n={args.oracle_n} cosine_floor={args.cosine_floor} "
          f"cold(visit<={args.cold_visit_max}, age>={args.cold_age_days}d)")
    print(f"  oracle corpus: full non-LoCoMo stack ({len(oracle_source_types)} source_types)")
    print(f"  queries scored: {summary['queries_scored']}/{summary['queries_total']} "
          f"(no cold-relevant: {summary['queries_no_cold_relevant']})")
    print(f"  {'layer':<14} {'cold_rec':>9} {'warm_rec':>9} {'rel_rec':>9} {'marg_cold':>10}")
    marg = summary["marginal_cold_lift"]
    prev_label: Optional[str] = None
    for label in layer_labels:
        m = summary["by_layer"].get(label, {})
        mk = f"{prev_label}->{label}"
        marg_s = _fmt_score(marg.get(mk), decimals=3) if prev_label else "    -   "
        print(f"  {label:<14} {_fmt_score(m.get('cold_relevant_recall'), decimals=3):>9} "
              f"{_fmt_score(m.get('warm_relevant_recall'), decimals=3):>9} "
              f"{_fmt_score(m.get('relevant_recall'), decimals=3):>9} {marg_s:>10}")
        prev_label = label
    if summary["cold_source_distribution"]:
        mix = ", ".join(f"{st}={n}" for st, n in summary["cold_source_distribution"].items())
        print(f"  cold-relevant atoms by source: {mix}")

    if not args.no_write:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        out = Path(args.output) if args.output else RUNS_DIR / f"wce_layers_{timestamp}.json"
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote {out}")
    return 0


def _run_promotion_replay(
    args: argparse.Namespace,
    queries: list[dict[str, Any]],
    default_k: int,
    payload: dict[str, Any],
    timestamp: str,
) -> int:
    """Promotion-policy replay (Lever B1): does promoting top-3 bury cold memory?"""
    k = args.k or default_k
    policies = [p.strip() for p in args.replay_policies.split(",") if p.strip()]
    unknown = [p for p in policies if p not in PROMOTION_POLICIES]
    if unknown:
        print(f"Unknown promotion policy(ies): {unknown}. Valid: {', '.join(PROMOTION_POLICIES)}",
              file=sys.stderr)
        return 2
    relgate_floor = args.replay_relgate_floor
    if relgate_floor is None:
        relgate_floor = args.cosine_floor
    retrieval_source_types = None if args.full_pool else resolve_continuity_source_types()

    with PgBridge() as pg:
        fixed = _fixed_oracle_sets(
            pg, queries,
            k=k,
            oracle_n=args.oracle_n,
            oracle_pool=args.oracle_pool,
            cosine_floor=args.cosine_floor,
            cold_visit_max=args.cold_visit_max,
            cold_age_days=args.cold_age_days,
            project=args.project,
            oracle_source_types=retrieval_source_types,
            continuity_grade=args.continuity_grade_oracle,
        )
        replay = run_promotion_replay(
            pg, fixed,
            policies=policies,
            rounds=args.replay_rounds,
            project=args.project,
            retrieval_source_types=retrieval_source_types,
            weight_cap=args.weight_cap,
            cosine_bypass=args.cosine_bypass,
            relgate_floor=relgate_floor,
        )

    config = {
        "k": k,
        "oracle_n": args.oracle_n,
        "oracle_pool": args.oracle_pool,
        "cosine_floor": args.cosine_floor,
        "cold_visit_max": args.cold_visit_max,
        "cold_age_days": args.cold_age_days,
        "project": args.project,
        "weight_cap": args.weight_cap,
        "rounds": args.replay_rounds,
        "relgate_floor": relgate_floor,
        "continuity_pool": "full" if args.full_pool else "curated",
        "retrieval_source_types": retrieval_source_types,
        "continuity_grade_oracle": args.continuity_grade_oracle,
    }
    payload["promotion_replay"] = {"config": config, "summary": replay}

    # ── Human-readable report ──
    print("\nWCE — promotion-policy replay (snapshot, rolled back; live cap ranker)")
    print(f"  config: k={k} rounds={args.replay_rounds} relgate_floor={relgate_floor} "
          f"cold(visit<={args.cold_visit_max}, age>={args.cold_age_days}d)")
    print(f"  retrieval pool: {config['continuity_pool']}"
          + (f" ({len(retrieval_source_types)} source_types)" if retrieval_source_types else ""))
    scored = next((m["queries_scored"] for m in replay["by_policy"].values()), 0)
    print(f"  queries scored: {scored}/{replay['queries_total']} "
          f"(embed-failed: {replay['queries_embed_failed']})")
    print(f"  {'policy':<10} {'cold_rec':>9} {'warm_rec':>9} {'rel_rec':>9} {'precision':>9} {'dcold_v3':>9}")
    deltas = replay["vs_top3_baseline"]
    for policy in policies:
        m = replay["by_policy"].get(policy, {})
        dc = deltas.get(policy, {}).get("cold_vs_top3") if policy != "top3" else 0.0
        base_tag = "  (baseline)" if policy == "top3" else ""
        print(f"  {policy:<10} {_fmt_score(m.get('cold_relevant_recall'), decimals=3):>9} "
              f"{_fmt_score(m.get('warm_relevant_recall'), decimals=3):>9} "
              f"{_fmt_score(m.get('relevant_recall'), decimals=3):>9} "
              f"{_fmt_score(m.get('surfacing_precision'), decimals=3):>9} "
              f"{_fmt_score(dc, decimals=3):>9}{base_tag}")

    if not args.no_write:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        out = Path(args.output) if args.output else RUNS_DIR / f"wce_promotion_{timestamp}.json"
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote {out}")
    return 0


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
    ap.add_argument("--layer-ablate", action="store_true",
                    help="memory-layer ablation B0-B3: attribute cold recall to handoff/KB/external "
                         "layers (fixed non-LoCoMo oracle, live cap ranker per layer)")
    ap.add_argument("--full-pool", action="store_true",
                    help="live retrieval uses full source-type table (default: curated B2-minus-intake)")
    ap.add_argument("--continuity-grade-oracle", action=argparse.BooleanOptionalAction, default=True,
                    help="define the oracle/cold/warm set over a continuity-grade corpus "
                         "(deny revelation/dark_matter/intake + dirty/pipe/revelation titles) so the "
                         "cold/warm axis is non-degenerate (~62/38, not ~83%% all-cold); "
                         "--no-continuity-grade-oracle reverts to the pre-fix degenerate oracle (default: on)")
    ap.add_argument("--promotion-replay", action="store_true",
                    help="Lever B1: replay the query stream under promotion policies on a "
                         "rolled-back snapshot; measure cold recall (does top-3 promotion bury cold memory?)")
    ap.add_argument("--replay-rounds", type=int, default=8,
                    help="promotion-replay: times to replay the query stream per policy (default: 8)")
    ap.add_argument("--replay-policies", default=",".join(PROMOTION_POLICIES),
                    help="promotion-replay: comma-separated policies "
                         f"({', '.join(PROMOTION_POLICIES)}); top3 is the live baseline")
    ap.add_argument("--replay-relgate-floor", type=float, default=None,
                    help="promotion-replay: cosine floor for the relgate policy (default: --cosine-floor)")
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

    if args.promotion_replay:
        return _run_promotion_replay(args, queries, default_k, payload, timestamp)

    if args.layer_ablate:
        return _run_layer_ablation(args, queries, default_k, payload, timestamp)

    retrieval_source_types = None if args.full_pool else resolve_continuity_source_types()
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
        "continuity_pool": "full" if args.full_pool else "curated",
        "retrieval_source_types": retrieval_source_types,
        "continuity_grade_oracle": args.continuity_grade_oracle,
    }

    results: list[dict[str, Any]] = []
    with PgBridge() as pg:
        eval_cfg = {
            k: v for k, v in config.items()
            if k not in (
                "variant_labels", "cap_sweep", "weight_cap", "cosine_bypass",
                "continuity_pool", "retrieval_source_types", "continuity_grade_oracle",
            )
        }
        for q in queries:
            results.append(
                evaluate_query(
                    pg, q,
                    weight_variants=weight_variants,
                    source_types=retrieval_source_types,
                    continuity_grade=args.continuity_grade_oracle,
                    **eval_cfg,
                )
            )

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
    pool_note = config.get("continuity_pool", "curated")
    n_types = len(config.get("retrieval_source_types") or [])
    print(f"  retrieval pool: {pool_note}" + (f" ({n_types} source_types)" if n_types else ""))
    print(f"  oracle corpus: {'continuity-grade' if config.get('continuity_grade_oracle') else 'full (degenerate axis)'}")
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
