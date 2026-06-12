#!/usr/bin/env python3
"""
scripts/bkt_seed_priors.py — Seed SOIL bkt collection with synthetic priors.

Run once after first deploy of core/bkt.py + core/skill_mastery.py to give
the BKT model a warm start for the known Fylgja skills rather than the cold
default (prior=0.25 for everything).

Priors are informed estimates based on observed session history — not fabricated
outcome sequences. BKT will refine them as real outcomes accumulate (every 25
opportunities triggers an EM refit from the actual history).

Usage:
    cd ~/github/willow-2.0
    python3 scripts/bkt_seed_priors.py [--dry-run] [--force]

    --dry-run   Print what would be written, skip SOIL writes.
    --force     Overwrite existing records (default: skip if already present).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from datetime import datetime, timezone

sys.path.insert(0, ".")

from core import bkt, soil

_COLLECTION = "bkt"

# Synthetic priors for the 7 Fylgja command skills.
# prior  = estimated P(already mastered) before any new opportunities
# learn  = P(unmastered -> mastered) per opportunity
# guess  = P(correct | not mastered) — kept above 0.15 for behavioural skills
# slip   = P(incorrect | mastered)  — lower = more reliable when mastered
#
# Rationale column: describes the observed session frequency and reliability
# that informed the prior estimate.
_SEEDS: list[dict] = [
    {
        "skill_id": "boot",
        "prior": 0.85, "learn": 0.05, "guess": 0.15, "slip": 0.05,
        "note": "Every session, protocol stable, rare deviation",
    },
    {
        "skill_id": "handoff",
        "prior": 0.80, "learn": 0.05, "guess": 0.15, "slip": 0.08,
        "note": "Every session, v2 schema now enforced",
    },
    {
        "skill_id": "shutdown",
        "prior": 0.80, "learn": 0.05, "guess": 0.15, "slip": 0.08,
        "note": "Every session, simple sentinel + stop sequence",
    },
    {
        "skill_id": "startup",
        "prior": 0.65, "learn": 0.10, "guess": 0.18, "slip": 0.10,
        "note": "Used when anchor is stale; more decision-heavy than boot",
    },
    {
        "skill_id": "willow-remote",
        "prior": 0.60, "learn": 0.12, "guess": 0.18, "slip": 0.10,
        "note": "Newer skill; used regularly but daemon/bwrap friction recurs",
    },
    {
        "skill_id": "release",
        "prior": 0.55, "learn": 0.12, "guess": 0.15, "slip": 0.12,
        "note": "Less frequent; multi-step process with VERSION/tag ordering",
    },
    {
        "skill_id": "cold-recovery",
        "prior": 0.40, "learn": 0.15, "guess": 0.20, "slip": 0.15,
        "note": "Rare; invoked only when context is degraded — high variance",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed(dry_run: bool = False, force: bool = False) -> None:
    skipped = 0
    written = 0

    for entry in _SEEDS:
        skill_id = entry["skill_id"]
        existing = soil.get(_COLLECTION, skill_id)
        if existing and not force:
            print(f"  skip  {skill_id:20s}  (already present — use --force to overwrite)")
            skipped += 1
            continue

        params = bkt.BKTParams(
            prior=entry["prior"],
            learn=entry["learn"],
            guess=entry["guess"],
            slip=entry["slip"],
        )
        record = {
            "skill_id": skill_id,
            "params": asdict(params),
            "p_known": params.prior,
            "p_next_correct": bkt.predict_correct(params.prior, params),
            "mastered": bkt.mastered(params.prior),
            "opportunities": 0,
            "history": [],
            "last_outcome_at": None,
            "refit_at": None,
            "seeded_at": _now(),
            "seed_note": entry["note"],
        }

        status = "dry"  if dry_run else "write"
        mastered_marker = " ✓mastered" if record["mastered"] else ""
        print(
            f"  {status:5s} {skill_id:20s}  prior={params.prior:.2f}"
            f"  p_next_correct={record['p_next_correct']:.3f}{mastered_marker}"
        )

        if not dry_run:
            soil.put(_COLLECTION, skill_id, record)
            written += 1

    print()
    print(f"  total: {written} written, {skipped} skipped"
          + (" (dry run)" if dry_run else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    print(f"BKT prior seeding — collection={_COLLECTION!r}"
          + (" [DRY RUN]" if args.dry_run else ""))
    print()
    seed(dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
