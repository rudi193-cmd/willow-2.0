#!/usr/bin/env python3
"""Source-type contribution sweep — find the curated retrieval pool that maximizes
cold-relevant recall, starting from the B2 peak (handoff+KB+external).

Reuses the WCE layer-ablation machinery (PR #516). Fixed oracle/cold set over the
full non-LoCoMo stack; vary the live cap@1.4 retrieval pool per source-type set.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core.embedder import embed
from core.pg_bridge import PgBridge
from willow.bench.continuity.run_wce import (
    DEFAULT_QUERIES,
    build_memory_layers,
    cosine_oracle,
    is_cold,
    is_warm,
    _recall_metrics,
)
from willow.ranking.continuity_pool import curated_continuity_source_types
from willow.ranking.hybrid import hybrid_search

K = 10
ORACLE_N = 20
ORACLE_POOL = 300
COSINE_FLOOR = 0.5
COLD_VISIT_MAX = 1
COLD_AGE_DAYS = 30.0


def load_queries():
    spec = json.loads(Path(DEFAULT_QUERIES).read_text(encoding="utf-8"))
    return [q for q in spec.get("queries", []) if isinstance(q, dict) and q.get("query")]


def build_targets(pg, queries, oracle_source_types):
    """Per query: embed + fixed oracle -> (qtext, qk, cold_ids, warm_ids, relevant_ids)."""
    now = datetime.now(timezone.utc)
    targets = []
    for q in queries:
        qtext = q["query"]
        qk = int(q.get("k", K))
        qvec = embed(qtext)
        if qvec is None:
            continue
        oracle = cosine_oracle(pg, qvec, project=None, oracle_pool=ORACLE_POOL,
                               source_types=oracle_source_types)
        relevant = [r for r in oracle[:ORACLE_N] if float(r["cosine"]) >= COSINE_FLOOR]
        cold = {r["id"] for r in relevant
                if is_cold(r, now, cold_visit_max=COLD_VISIT_MAX, cold_age_days=COLD_AGE_DAYS)}
        warm = {r["id"] for r in relevant
                if is_warm(r, now, cold_visit_max=COLD_VISIT_MAX, cold_age_days=COLD_AGE_DAYS)}
        rel = {r["id"] for r in relevant}
        if cold:
            targets.append((qtext, qk, cold, warm, rel))
    return targets


def pool_recall(pg, targets, source_types):
    """Mean cold/warm/relevant recall for a retrieval pool restricted to source_types."""
    cold_vals, warm_vals, rel_vals = [], [], []
    for qtext, qk, cold_ids, warm_ids, rel_ids in targets:
        hits = hybrid_search(qtext, pg, limit=qk, source_types=source_types)
        m = _recall_metrics([h["id"] for h in hits], k=qk,
                            cold_ids=cold_ids, warm_ids=warm_ids, relevant_ids=rel_ids)
        if m["cold_relevant_recall"] is not None:
            cold_vals.append(m["cold_relevant_recall"])
        if m["warm_relevant_recall"] is not None:
            warm_vals.append(m["warm_relevant_recall"])
        if m["relevant_recall"] is not None:
            rel_vals.append(m["relevant_recall"])
    mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else None  # noqa: E731
    return mean(cold_vals), mean(warm_vals), mean(rel_vals)


def main():
    with PgBridge() as pg:
        layers = dict(build_memory_layers(pg))
        b2 = list(layers["B2_external"])
        curated = curated_continuity_source_types()
        full = list(layers["B3_full"])
        tail = sorted(set(full) - set(b2))
        targets = build_targets(pg, load_queries(), full)
        print(f"targets (queries with cold-relevant): {len(targets)}")
        print(f"B2 size={len(b2)} curated size={len(curated)} full size={len(full)} tail size={len(tail)}\n")

        base_cold, base_warm, base_rel = pool_recall(pg, targets, b2)
        curated_cold, curated_warm, curated_rel = pool_recall(pg, targets, curated)
        full_cold, full_warm, full_rel = pool_recall(pg, targets, full)
        print(f"BASELINE  B2(handoff+KB+external)  cold={base_cold} warm={base_warm} rel={base_rel}")
        print(f"WINNER    curated(B2-intake)       cold={curated_cold} warm={curated_warm} rel={curated_rel}")
        print(f"BASELINE  B3(full non-LoCoMo)       cold={full_cold} warm={full_warm} rel={full_rel}\n")

        # Leave-one-out from B2: which B2 types are load-bearing for cold recall?
        print("== LEAVE-ONE-OUT from B2 (cold delta when type removed; negative = type helps) ==")
        loo = []
        for s in b2:
            pool = [x for x in b2 if x != s]
            c, w, _ = pool_recall(pg, targets, pool)
            loo.append((round((c or 0) - (base_cold or 0), 4), s, c, w))
        for d, s, c, w in sorted(loo):
            print(f"  -{s:<22} cold={c} (Δ{d:+.4f}) warm={w}")

        # Add-one-in to B2: which tail types help vs hurt cold recall?
        print("\n== ADD-ONE-IN to B2 (cold delta when tail type added; positive = helps) ==")
        aoi = []
        for s in tail:
            pool = b2 + [s]
            c, w, _ = pool_recall(pg, targets, pool)
            aoi.append((round((c or 0) - (base_cold or 0), 4), s, c, w))
        for d, s, c, w in sorted(aoi, reverse=True):
            print(f"  +{s:<22} cold={c} (Δ{d:+.4f}) warm={w}")

        # Greedy forward selection from B2 over tail types (maximize cold, keep warm>=base-0.035).
        print("\n== GREEDY forward selection from B2 (add best positive marginal) ==")
        pool = list(b2)
        cur_cold, cur_warm = base_cold, base_warm
        warm_floor = (base_warm or 0) - 0.035
        added = []
        remaining = list(tail)
        while True:
            best = None
            for s in remaining:
                c, w, _ = pool_recall(pg, targets, pool + [s])
                if w is not None and w < warm_floor:
                    continue
                if c is not None and (best is None or c > best[0]):
                    best = (c, w, s)
            if best is None or best[0] <= (cur_cold or 0):
                break
            cur_cold, cur_warm, s = best
            pool.append(s)
            added.append(s)
            remaining.remove(s)
            print(f"  + {s:<22} cold={cur_cold} warm={cur_warm}")
        print(f"\nGREEDY result: cold={cur_cold} warm={cur_warm}  (+{round((cur_cold or 0)-(base_cold or 0),4)} vs B2, "
              f"+{round((cur_cold or 0)-(full_cold or 0),4)} vs full)")
        print(f"added types: {added or '(none — B2 is already optimal)'}")


if __name__ == "__main__":
    main()
