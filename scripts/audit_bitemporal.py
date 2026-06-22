#!/usr/bin/env python3
"""audit_bitemporal.py — verify supersede-not-delete invariants on knowledge.

Audit PR 6 (operator work order, rev 5): promotion must be bi-temporal —
superseding sets invalid_at on the old atom; nothing is deleted. This audit
verifies the two directions of that invariant:

1. every atom with tier='superseded' carries invalid_at
2. every atom with invalid_at set carries tier='superseded'

Plus a summary of tier/validity distribution. Exit 1 when violations exist.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from core.pg_bridge import get_connection, release_connection


def main() -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM knowledge WHERE tier='superseded' AND invalid_at IS NULL"
            )
            superseded_without_invalid = cur.fetchone()[0]

            cur.execute(
                "SELECT count(*) FROM knowledge WHERE invalid_at IS NOT NULL AND tier <> 'superseded'"
            )
            invalid_without_superseded = cur.fetchone()[0]

            cur.execute(
                "SELECT tier, count(*) FILTER (WHERE invalid_at IS NULL) AS live, "
                "count(*) FILTER (WHERE invalid_at IS NOT NULL) AS closed "
                "FROM knowledge GROUP BY tier ORDER BY tier"
            )
            distribution = cur.fetchall()
    finally:
        release_connection(conn)

    print("[bitemporal] tier distribution (live / closed):")
    for tier, live, closed in distribution:
        print(f"  {tier:<12} {live:>6} / {closed}")

    violations = 0
    if superseded_without_invalid:
        violations += superseded_without_invalid
        print(f"[bitemporal] VIOLATION: {superseded_without_invalid} atoms "
              "tier='superseded' but invalid_at is NULL")
    if invalid_without_superseded:
        violations += invalid_without_superseded
        print(f"[bitemporal] VIOLATION: {invalid_without_superseded} atoms "
              "have invalid_at set but tier != 'superseded'")

    if violations:
        print(f"[bitemporal] {violations} violations — supersede-not-delete invariant broken")
        return 1
    print("[bitemporal] OK — supersede-not-delete invariants hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
