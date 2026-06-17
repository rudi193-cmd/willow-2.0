#!/usr/bin/env python3
"""
signal_weight_updater.py — norn-pass: adjust KB atom weights from signal valence.

Signal-promoted atoms (category in correction/preference/confirmation/
scope_redirect/tool_denial) receive a weight calculated from their confidence
(set at promotion time to reflect signal strength) multiplied by a time-decay
factor and a per-category multiplier.

Weight formula:
    decay    = e^(-ln(2) * age_days / WEIGHT_HALF_LIFE_DAYS)
    weight   = confidence × decay × category_multiplier
    clamped  = max(WEIGHT_MIN, weight)

Interpretation:
  - Fresh correction (confidence=0.9, age=0d) → weight ≈ 1.17
  - Week-old correction (confidence=0.9, age=7d)  → weight ≈ 0.82
  - Month-old correction (confidence=0.9, age=14d) → weight ≈ 0.59
  - Atom eventually sinks below 1.0 and no longer dominates non-signal hits

Category multipliers (relative importance in retrieval):
  correction    : 1.3  (highest — agent must recall behavioral rails)
  tool_denial   : 1.25 (high — structural block patterns)
  scope_redirect: 1.15 (mid  — direction changes in current work)
  preference    : 1.1  (mid  — user-stated standing preferences)
  confirmation  : 1.1  (mid  — positive signal, reinforce what works)

Usage:
    python3 scripts/signal_weight_updater.py [--dry-run] [--category CAT]
"""
from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from core.agent_identity import require_agent_name

AGENT = require_agent_name()

SIGNAL_CATEGORIES = (
    "correction",
    "preference",
    "confirmation",
    "scope_redirect",
    "tool_denial",
)

CATEGORY_MULTIPLIER: dict[str, float] = {
    "correction":     1.30,
    "tool_denial":    1.25,
    "scope_redirect": 1.15,
    "preference":     1.10,
    "confirmation":   1.10,
}

WEIGHT_HALF_LIFE_DAYS: float = 14.0  # faster decay than signal promotion (30d)
WEIGHT_MIN: float = 0.3              # floor — signal atoms never fully disappear


def _time_decay(created_at: datetime) -> float:
    """Exponential decay from atom creation. 14-day half-life."""
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (datetime.now(timezone.utc) - created_at).total_seconds() / 86400)
    return math.exp(-math.log(2) * age_days / WEIGHT_HALF_LIFE_DAYS)


def _target_weight(confidence: float, created_at: datetime, category: str) -> float:
    multiplier = CATEGORY_MULTIPLIER.get(category, 1.0)
    raw = confidence * _time_decay(created_at) * multiplier
    return round(max(WEIGHT_MIN, raw), 4)


def run(dry_run: bool = False, category_filter: str | None = None) -> dict:
    from core.pg_bridge import PgBridge

    categories = (category_filter,) if category_filter else SIGNAL_CATEGORIES

    with PgBridge() as pg:
        # Fetch signal atoms
        placeholders = ",".join(["%s"] * len(categories))
        with pg.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, category, confidence, created_at, weight
                FROM knowledge
                WHERE category IN ({placeholders})
                  AND invalid_at IS NULL
                ORDER BY category, created_at DESC
                """,
                categories,
            )
            rows = cur.fetchall()

        if not rows:
            print(f"[weight-updater] no signal atoms found for {categories}")
            return {"updated": 0, "skipped": 0}

        print(f"[weight-updater] {len(rows)} signal atoms found")

        updated = skipped = 0
        for atom_id, cat, confidence, created_at, current_weight in rows:
            new_weight = _target_weight(float(confidence or 0.5), created_at, cat)
            delta = abs(new_weight - float(current_weight or 1.0))

            if delta < 0.001:
                skipped += 1
                continue

            direction = "↑" if new_weight > float(current_weight or 1.0) else "↓"
            if dry_run:
                print(
                    f"  [dry-run] {atom_id[:12]} {cat:15s} "
                    f"conf={confidence:.3f} {current_weight:.3f} → {new_weight:.3f} {direction}"
                )
                updated += 1
                continue

            with pg.conn.cursor() as cur:
                cur.execute(
                    "UPDATE knowledge SET weight = %s, updated_at = now() WHERE id = %s",
                    (new_weight, atom_id),
                )
            pg.conn.commit()
            print(
                f"  [updated] {atom_id[:12]} {cat:15s} "
                f"conf={confidence:.3f} {current_weight:.3f} → {new_weight:.3f} {direction}"
            )
            updated += 1

    print(f"[weight-updater] done — updated={updated} skipped={skipped} (delta<0.001)")
    return {"updated": updated, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description="Adjust KB atom weights from signal valence")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--category", choices=list(SIGNAL_CATEGORIES),
        help="Update only this category (default: all signal categories)",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, category_filter=args.category)


if __name__ == "__main__":
    main()
