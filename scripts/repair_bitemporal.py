#!/usr/bin/env python3
"""repair_bitemporal.py — restore the supersede-not-delete invariant on knowledge.

Counterpart to scripts/audit_bitemporal.py. That audit flags two directions of
violation; this repairs both, supersede-not-delete (nothing is removed):

  A. tier='superseded' AND invalid_at IS NULL
     → set invalid_at = updated_at (the supersession moment; the row's last
       modification WAS the tier flip). Falls back to now() if updated_at is
       NULL, logging which ids used the fallback.

  B. invalid_at IS NOT NULL AND tier <> 'superseded'
     → set tier='superseded'. The atom is already temporally closed (live
       queries exclude it); only the tier label lagged.

Reversible: on --apply the full before-state (id, old tier, old invalid_at) is
captured into a FRANK ledger 'bitemporal_repair' entry before the UPDATEs run.

Usage:
    python3 scripts/repair_bitemporal.py            # dry-run (default)
    python3 scripts/repair_bitemporal.py --apply    # perform + ledger record
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from core.pg_bridge import get_connection, release_connection  # noqa: E402

# Selection SQL — must mirror audit_bitemporal.py exactly, or the repair and the
# audit can silently disagree about what a violation is.
SEL_A = "tier='superseded' AND invalid_at IS NULL"
SEL_B = "invalid_at IS NOT NULL AND tier <> 'superseded'"


def _rows(cur, where: str) -> list:
    cur.execute(
        f"SELECT id, tier, invalid_at, updated_at FROM knowledge WHERE {where} ORDER BY id"
    )
    return cur.fetchall()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Repair bitemporal supersede-not-delete violations")
    ap.add_argument("--apply", action="store_true", help="perform the repair (default: dry-run)")
    args = ap.parse_args(argv)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            a_rows = _rows(cur, SEL_A)
            b_rows = _rows(cur, SEL_B)
    finally:
        release_connection(conn)

    a_fallback = [r[0] for r in a_rows if r[3] is None]
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[bitemporal-repair {mode}]")
    print(f"  A. superseded w/o invalid_at : {len(a_rows)} → invalid_at = updated_at"
          + (f" ({len(a_fallback)} fall back to now())" if a_fallback else ""))
    if a_fallback:
        print(f"     now()-fallback ids: {', '.join(a_fallback)}")
    print(f"  B. invalid_at w/o superseded : {len(b_rows)} → tier = 'superseded'")

    if not args.apply:
        print(f"{mode}: {len(a_rows) + len(b_rows)} rows would change — re-run with --apply")
        return 0

    if not (a_rows or b_rows):
        print("APPLY: nothing to repair — invariant already holds")
        return 0

    # Capture before-state for reversibility, then repair, then ledger.
    before = {
        "A_superseded_no_invalid": [
            {"id": r[0], "old_invalid_at": str(r[2]), "set_invalid_at": str(r[3])}
            for r in a_rows
        ],
        "B_invalid_no_superseded": [
            {"id": r[0], "old_tier": r[1], "old_invalid_at": str(r[2])} for r in b_rows
        ],
    }

    # Record the reversible before-state in FRANK *before* mutating, so the
    # ledger captures the pre-repair truth even if the UPDATE is interrupted.
    from core.pg_bridge import PgBridge
    pg = PgBridge()
    try:
        pg.ledger_append(
            "willow",
            "bitemporal_repair",
            {
                "summary": (
                    f"Repairing {len(a_rows) + len(b_rows)} supersede-not-delete "
                    f"violations: {len(a_rows)} superseded atoms → invalid_at=updated_at; "
                    f"{len(b_rows)} invalidated atoms → tier=superseded. No deletes."
                ),
                "a_count": len(a_rows),
                "b_count": len(b_rows),
                "now_fallback_ids": a_fallback,
                "before": before,
            },
        )
        print("APPLY: before-state recorded in FRANK ledger (bitemporal_repair)")
    except Exception as e:
        print(f"APPLY: ABORT — ledger record failed, no rows changed: {e}", file=sys.stderr)
        return 1

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE knowledge SET invalid_at = COALESCE(updated_at, now()) WHERE {SEL_A}"
            )
            a_done = cur.rowcount
            cur.execute(f"UPDATE knowledge SET tier = 'superseded' WHERE {SEL_B}")
            b_done = cur.rowcount
        conn.commit()
    finally:
        release_connection(conn)

    print(f"APPLY: set invalid_at on {a_done}; set tier=superseded on {b_done}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
