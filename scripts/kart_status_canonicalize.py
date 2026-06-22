#!/usr/bin/env python3
"""Canonicalize Kart task status vocabulary: legacy ``complete`` -> ``completed``.

The Kart task writer settled on ``completed`` as the success status, but ~216
legacy rows (all written 2026-05-24..05-29, before the writer was canonical)
carry the bare ``complete``. Two success vocabularies make any consumer that
filters on one silently under-count — e.g. ``willow/fylgja/desk_attention.py``
filters ``status IN ('done', 'completed')`` and drops ``complete`` rows.

No live writer emits bare ``complete`` (verified), so this is a one-time data
migration, not a behavior change. Idempotent — a no-op once the table is clean.

    python3 scripts/kart_status_canonicalize.py            # apply
    python3 scripts/kart_status_canonicalize.py --dry-run  # report only
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
os.environ.setdefault("WILLOW_PG_DB", "willow_20")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Canonicalize Kart task status 'complete' -> 'completed'"
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="report rows that would change; write nothing",
    )
    args = ap.parse_args()

    from core.pg_bridge import PgBridge

    pg = PgBridge()
    pg._ensure_conn()
    with pg.conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM tasks WHERE status = 'complete'")
        before = cur.fetchone()[0]
        print(f"legacy 'complete' rows: {before}")
        if before == 0:
            print("already canonical — nothing to do.")
            return 0
        if args.dry_run:
            print(f"[dry-run] would set {before} rows 'complete' -> 'completed'")
            return 0
        cur.execute("UPDATE tasks SET status = 'completed' WHERE status = 'complete'")
        changed = cur.rowcount
        pg.conn.commit()
        cur.execute("SELECT count(*) FROM tasks WHERE status = 'complete'")
        after = cur.fetchone()[0]

    print(f"updated {changed} rows; remaining 'complete': {after}")
    return 0 if after == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
