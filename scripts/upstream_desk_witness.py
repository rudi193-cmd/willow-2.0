#!/usr/bin/env python3
"""Upstream desk weekly witness — queue maintainer heatmap + promise ledger via Kart.

Scheduled weekly by ``systemd/willow-upstream-desk.timer``. Run manually:

    ./willow.sh upstream-desk
    python3 scripts/upstream_desk_witness.py --force
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SENDER = os.environ.get("WILLOW_AGENT_NAME", "willow")
REPORT_CHANNEL = os.environ.get("UPSTREAM_DESK_REPORT_CHANNEL", "upstream")


def _post_grove(content: str, *, dry_run: bool) -> None:
    if dry_run:
        print(f"[grove dry-run] #{REPORT_CHANNEL}: {content}")
        return
    try:
        from core.grove_db import bus_send, get_connection, release_connection

        conn = get_connection()
        try:
            bus_send(
                conn,
                channel_name=REPORT_CHANNEL,
                sender=SENDER,
                content=content,
                bus_type="EVENT",
                priority=4,
            )
        finally:
            release_connection(conn)
        print(f"[grove] report posted to #{REPORT_CHANNEL}")
    except Exception as exc:  # noqa: BLE001
        print(f"[grove] report post FAILED ({type(exc).__name__}: {exc})", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="Upstream desk weekly witness (Kart scheduler)")
    ap.add_argument("--force", action="store_true", help="queue even if interval not elapsed")
    ap.add_argument("--check-first", action="store_true", help="skip unless upstream_desk_conditions due")
    ap.add_argument("--dry-run", action="store_true", help="no SOIL lock / Kart queue / Grove")
    args = ap.parse_args()

    from core import soil
    from core.upstream_desk_state import (
        queue_upstream_desk_task,
        upstream_desk_conditions,
    )

    if args.check_first and not args.force:
        check = upstream_desk_conditions(soil)
        if not check.get("should_run"):
            print(f"upstream desk skipped: {check.get('reason')}")
            return 0

    if args.dry_run:
        print("upstream desk dry-run: would queue Kart batch upstream_desk_intel.py --emit-soil")
        return 0

    try:
        from core.pg_bridge import PgBridge

        with PgBridge() as pg:
            task_id = queue_upstream_desk_task(pg, submitted_by=SENDER)
    except Exception as exc:  # noqa: BLE001
        print(f"upstream desk witness FAILED ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 1

    if not task_id:
        print("upstream desk witness FAILED — Kart submit returned no task_id", file=sys.stderr)
        return 1

    line = f"upstream desk queued Kart task {task_id} (heatmap + promise ledger)"
    print(line)
    if not args.dry_run:
        _post_grove(line, dry_run=False)
    else:
        _post_grove(line, dry_run=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
