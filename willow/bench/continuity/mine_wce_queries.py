#!/usr/bin/env python3
"""
mine_wce_queries.py — build an expanded, power-filtered WCE probe set from real
fleet signal instead of hand-authored scenarios.
b17: WCE2  ΔΣ=42

Why
---
The v1 probe set is 12 hand-picked real topics (wce_queries.json _comment flags
this: "revisit with mined session topics"). n=12 with tiny per-query cold sets
cannot resolve the ~2pp effects WCE chases (see KB 9F3D0DF6 — the promotion
replay was noise-dominated at n=12). This miner grows the set from REAL signal
and selects on statistical POWER, not on ranker performance.

Sources (real, not authored)
----------------------------
  spine   — handoff machine blocks (open_threads / next_steps / key_actions):
            the canonical "what the next session needs to retrieve" phrases.
  widen   — substantive session_messages (real queries agents/users issued),
            minus procedural chatter (merge/babysit/PR #/todos…).

Selection = POWER filter, NOT teaching-to-test
----------------------------------------------
For each candidate we run the SAME recency-blind cosine oracle the harness uses
(cosine_oracle over the continuity-grade corpus, oracle_n=20, cosine_floor=0.5,
cold = visit<=1 & (never|>=age)), and keep only candidates that are BURIAL-
TESTABLE: >= min_cold cold-relevant atoms (a scoreable cold set) AND >= min_warm
warm-relevant atoms (warm competitors that can actually do the burying). Ranking
by max cold-set size alone (the v1 objective) is a trap — it pulls the vaguest,
most-diffuse queries (whose top-20 neighbours are ALL cold) to the top, which is
exactly where burial is UNobservable and where conversational chatter lands. We
instead rank by balance — min(n_cold, n_warm) — so the kept probes have both a
fat cold set to score recall on and a real warm population to bury it. Both
counts are independent of whether the live ranker retrieves the atoms, so this
does not bias the recall measurement. Near-duplicate queries are dropped by
query-embedding cosine.

Usage
-----
  python3 willow/bench/continuity/mine_wce_queries.py --target 50 --min-cold 3
  python3 willow/bench/continuity/mine_wce_queries.py --dry-run   # report, no write
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BENCH_DIR = Path(__file__).resolve().parent
WILLOW_ROOT = Path(os.environ.get("WILLOW_ROOT", str(BENCH_DIR.parent.parent.parent)))
OUT_FILE = BENCH_DIR / "wce_queries.json"
sys.path.insert(0, str(WILLOW_ROOT))

from core.embedder import embed  # noqa: E402
from core.pg_bridge import PgBridge  # noqa: E402
from run_wce import cosine_oracle, is_cold, is_warm  # noqa: E402  (same dir)

# Phrases that are procedural/meta, not knowledge topics — dropped pre-embed.
_GENERIC = re.compile(
    r"\b(ask sean|orient via|unnamed|tbd|deferred until|next thread|see above|"
    r"babysit|merge when green|squash|delete[- ]branch|rebase|cleanup|"
    r"run through|rebuild the todos|pr #?\d+|kart task|poll|re-?check|"
    r"push|commit|worktree|gh pr)\b",
    re.I,
)
_WORDISH = re.compile(r"[A-Za-z]{3,}")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip(" .!?-•—\t")


def _is_topical(text: str, *, min_words: int = 4, max_words: int = 32) -> bool:
    t = _clean(text)
    n = len(t.split())
    if n < min_words or n > max_words:
        return False
    if _GENERIC.search(t):
        return False
    return len(_WORDISH.findall(t)) >= min_words  # mostly real words, not IDs/symbols


def _handoff_candidates(limit_files: int) -> list[dict[str, Any]]:
    home = os.environ.get("WILLOW_HOME", os.path.expanduser("~/github/.willow"))
    files = sorted(glob.glob(os.path.join(home, "handoffs", "**", "*.md"), recursive=True))
    files = files[-limit_files:] if limit_files else files
    out: list[dict[str, Any]] = []
    for fp in files:
        try:
            txt = Path(fp).read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        m = re.search(r"```json\s*(\{.*?\})\s*```", txt, re.S)
        if not m:
            continue
        try:
            mb = json.loads(m.group(1))
        except Exception:
            continue
        for field in ("open_threads", "next_steps", "key_actions"):
            for item in (mb.get(field) or []):
                phrase = _clean(str(item))
                if _is_topical(phrase):
                    out.append({"query": phrase, "source": f"handoff:{field}",
                                "origin": os.path.basename(fp)})
    return out


def _message_candidates(pg: PgBridge, limit: int) -> list[dict[str, Any]]:
    pg._ensure_conn()
    with pg.conn.cursor() as cur:
        cur.execute(
            "SELECT text FROM session_messages "
            "WHERE text IS NOT NULL AND char_length(text) BETWEEN 25 AND 240 "
            "ORDER BY timestamp DESC LIMIT %s",
            (limit,),
        )
        rows = [r[0] for r in cur.fetchall()]
    out = []
    for t in rows:
        phrase = _clean(t)
        if _is_topical(phrase):
            out.append({"query": phrase, "source": "session_message", "origin": "session_messages"})
    return out


def _slug(text: str, taken: set[str]) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    base = "-".join(words[:5])[:48] or "probe"
    slug, i = base, 2
    while slug in taken:
        slug = f"{base}-{i}"
        i += 1
    taken.add(slug)
    return slug


def main() -> int:
    ap = argparse.ArgumentParser(description="Mine an expanded WCE probe set from real fleet signal.")
    ap.add_argument("--target", type=int, default=50, help="target probe count")
    ap.add_argument("--min-cold", type=int, default=3, help="keep candidates with >= this many cold-relevant atoms")
    ap.add_argument("--min-warm", type=int, default=2,
                    help="keep candidates with >= this many WARM-relevant atoms (warm competitors "
                         "that can bury the cold set); 0 disables — burial is unobservable without them")
    ap.add_argument("--oracle-n", type=int, default=20)
    ap.add_argument("--oracle-pool", type=int, default=300)
    ap.add_argument("--cosine-floor", type=float, default=0.5)
    ap.add_argument("--cold-visit-max", type=int, default=1)
    ap.add_argument("--cold-age-days", type=float, default=30.0)
    ap.add_argument("--continuity-grade-oracle", action=argparse.BooleanOptionalAction, default=True,
                    help="power-filter over the continuity-grade oracle corpus (deny "
                         "revelation/dark_matter/intake + dirty/pipe/revelation titles); matches the "
                         "non-degenerate cold/warm axis run_wce.py now baselines on (default: on)")
    ap.add_argument("--handoff-files", type=int, default=160, help="most-recent N handoff files to mine")
    ap.add_argument("--message-scan", type=int, default=1500, help="most-recent N session messages to scan")
    ap.add_argument("--dedup-cosine", type=float, default=0.88, help="drop a probe if query-cosine to a kept one exceeds this")
    ap.add_argument("--max-message-share", type=float, default=0.4, help="cap message-sourced probes to this fraction")
    ap.add_argument("--dry-run", action="store_true", help="report only; do not write wce_queries.json")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    with PgBridge() as pg:
        cands = _handoff_candidates(args.handoff_files) + _message_candidates(pg, args.message_scan)
        # de-dup identical query strings, prefer handoff source
        seen_txt: dict[str, dict] = {}
        for c in cands:
            key = c["query"].lower()
            if key not in seen_txt or (c["source"].startswith("handoff") and not seen_txt[key]["source"].startswith("handoff")):
                seen_txt[key] = c
        cands = list(seen_txt.values())
        print(f"candidates after text-dedup: {len(cands)} "
              f"(handoff={sum(1 for c in cands if c['source'].startswith('handoff'))}, "
              f"message={sum(1 for c in cands if c['source']=='session_message')})")

        # embed + oracle power-filter
        kept: list[dict[str, Any]] = []
        for c in cands:
            qvec = embed(c["query"])
            if qvec is None:
                continue
            oracle = cosine_oracle(
                pg, qvec, project=None, oracle_pool=args.oracle_pool,
                continuity_grade=args.continuity_grade_oracle,
            )
            relevant = [r for r in oracle[:args.oracle_n] if float(r["cosine"]) >= args.cosine_floor]
            n_cold = sum(
                1 for r in relevant
                if is_cold(r, now, cold_visit_max=args.cold_visit_max, cold_age_days=args.cold_age_days)
            )
            n_warm = sum(
                1 for r in relevant
                if is_warm(r, now, cold_visit_max=args.cold_visit_max, cold_age_days=args.cold_age_days)
            )
            if n_cold >= args.min_cold and n_warm >= args.min_warm:
                c["_qvec"] = qvec
                c["n_cold_relevant"] = n_cold
                c["n_warm_relevant"] = n_warm
                c["n_relevant"] = len(relevant)
                kept.append(c)
        print(f"passed power-filter (n_cold>={args.min_cold} & n_warm>={args.min_warm}): {len(kept)}")

    # rank by cold-set size, then dedup near-duplicate queries by embedding cosine
    import math

    def cos(a, b):
        s = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return s / (na * nb) if na and nb else 0.0

    # Rank by burial-testability balance: queries with both a fat cold set AND a
    # real warm population first. min(cold, warm) avoids the v1 max-cold trap that
    # surfaced vague/chatter probes whose top-20 neighbours were all cold.
    kept.sort(key=lambda c: (
        -min(c["n_cold_relevant"], c["n_warm_relevant"]),
        -(c["n_cold_relevant"] + c["n_warm_relevant"]),
        c["source"],
    ))
    selected: list[dict[str, Any]] = []
    msg_cap = int(args.target * args.max_message_share)
    msg_count = 0
    for c in kept:
        if len(selected) >= args.target:
            break
        if c["source"] == "session_message" and msg_count >= msg_cap:
            continue
        if any(cos(c["_qvec"], s["_qvec"]) > args.dedup_cosine for s in selected):
            continue
        selected.append(c)
        if c["source"] == "session_message":
            msg_count += 1

    taken: set[str] = set()
    queries = [
        {
            "id": _slug(c["query"], taken),
            "query": c["query"],
            "k": 10,
            "_source": c["source"],
            "_origin": c["origin"],
            "_n_cold_relevant_at_mint": c["n_cold_relevant"],
            "_n_warm_relevant_at_mint": c["n_warm_relevant"],
        }
        for c in selected
    ]
    cold_sizes = [q["_n_cold_relevant_at_mint"] for q in queries]
    warm_sizes = [q["_n_warm_relevant_at_mint"] for q in queries]

    def _stats(xs: list[int]) -> dict[str, Any]:
        return {
            "min": min(xs) if xs else 0,
            "max": max(xs) if xs else 0,
            "mean": round(sum(xs) / len(xs), 2) if xs else 0,
        }

    payload = {
        "_comment": (
            "WCE cold-relevant recall probe set v2 — MINED from real fleet signal "
            "(handoff machine blocks as spine + substantive session_messages to widen), "
            "filtered to BURIAL-TESTABLE candidates (n_cold>=%d & n_warm>=%d) over the "
            "continuity-grade cosine oracle and ranked by min(cold,warm) balance — not by "
            "max cold-set size (the v1 trap that surfaced vague all-cold chatter), and not "
            "by ranker performance (not teaching-to-test). v1 (12 hand-picked) is in git "
            "history. Mined %s."
            % (args.min_cold, args.min_warm, now.strftime("%Y-%m-%dT%H:%M:%SZ"))
        ),
        "default_k": 10,
        "_provenance": {
            "miner": "mine_wce_queries.py",
            "min_cold": args.min_cold,
            "min_warm": args.min_warm,
            "oracle_n": args.oracle_n,
            "continuity_grade_oracle": args.continuity_grade_oracle,
            "cosine_floor": args.cosine_floor,
            "cold": f"visit<={args.cold_visit_max} & (never|>={args.cold_age_days}d)",
            "ranking": "min(n_cold, n_warm) desc, then (n_cold+n_warm) desc",
            "n_probes": len(queries),
            "source_mix": {
                "handoff": sum(1 for q in queries if q["_source"].startswith("handoff")),
                "session_message": sum(1 for q in queries if q["_source"] == "session_message"),
            },
            "cold_set_size": _stats(cold_sizes),
            "warm_set_size": _stats(warm_sizes),
        },
        "queries": queries,
    }

    print(f"\nselected {len(queries)} probes "
          f"(handoff={payload['_provenance']['source_mix']['handoff']}, "
          f"message={payload['_provenance']['source_mix']['session_message']})")
    print(f"cold-set size: {payload['_provenance']['cold_set_size']}")
    print(f"warm-set size: {payload['_provenance']['warm_set_size']}")
    for q in queries[:12]:
        print(f"  [{q['_n_cold_relevant_at_mint']:>2}c/{q['_n_warm_relevant_at_mint']:>2}w] "
              f"{q['_source']:<18} {q['query'][:66]}")

    if args.dry_run:
        print("\n--dry-run: not writing")
        return 0
    OUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {OUT_FILE} ({len(queries)} probes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
