#!/usr/bin/env python3
"""Backfill public.edges from approved/active binder_edges (idempotent)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.pg_bridge import PgBridge


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync binder_edges → public.edges")
    ap.add_argument("--limit", type=int, default=500, help="Max binder edges to process")
    args = ap.parse_args()
    pg = PgBridge()
    result = pg.binder_backfill_postgres_edges(limit=args.limit)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
