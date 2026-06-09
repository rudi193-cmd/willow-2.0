#!/usr/bin/env python3
"""human_required_report.py — grouped human-required queue report with KB atom links."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    ps = str(p)
    if ps not in sys.path:
        sys.path.insert(0, ps)

from core.human_required import KINDS, list_items, stats  # noqa: E402
from core.pg_bridge import PgBridge, run_migrations  # noqa: E402

CLOSE_CRITERIA: dict[str, str] = {
    "needs_consent": "Operator explicitly consents; durable write path records consent stamp.",
    "needs_attestation": "Human attestation workflow exists and elevated tier promotion requires it.",
    "needs_review": "Named human reviewer signs off; linked KB atom updated or queue item resolved.",
    "operator_overload": "Operator load becomes a first-class routing signal in desk/comfort surfaces.",
    "external_onboarding": "Unified onboarding contract exists with roles, consent, and support path.",
}


def _lookup_kb_atom(conn, source_ref: str) -> dict | None:
    if not source_ref:
        return None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, project, tier
            FROM knowledge
            WHERE invalid_at IS NULL AND id = %s
            LIMIT 1
            """,
            (source_ref,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "title": row[1], "project": row[2], "tier": row[3]}


def build_report(conn, *, status: str = "open", limit: int = 100) -> dict:
    summary = stats(conn)
    items = list_items(conn, status=status, limit=limit)

    by_kind: dict[str, list] = defaultdict(list)
    by_priority: dict[str, list] = defaultdict(list)
    enriched = []

    for item in items:
        source_ref = item.get("source_ref") or ""
        kb_atom = _lookup_kb_atom(conn, source_ref)
        entry = {
            **item,
            "kb_atom": kb_atom,
            "close_criteria": CLOSE_CRITERIA.get(item.get("kind", ""), "Resolve with operator note."),
            "linked_via": "source_ref->knowledge.id" if kb_atom else None,
        }
        enriched.append(entry)
        by_kind[item.get("kind", "unknown")].append(entry)
        by_priority[item.get("priority", "normal")].append(entry)

    stale_high = [
        e for e in enriched
        if e.get("priority") in {"high", "critical"} and not e.get("assignee")
    ]

    return {
        "stats": summary,
        "close_criteria_by_kind": CLOSE_CRITERIA,
        "by_kind": {k: len(v) for k, v in by_kind.items()},
        "by_priority": {k: len(v) for k, v in by_priority.items()},
        "stale_high_without_assignee": stale_high,
        "items": enriched,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Human-required queue report")
    parser.add_argument("--status", default="open", choices=("open", "acknowledged", "resolved", "dismissed"))
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    pg = PgBridge()
    run_migrations(pg.conn)
    try:
        report = build_report(pg.conn, status=args.status, limit=args.limit)
        print(json.dumps(report, indent=2, default=str))

        stale = report.get("stale_high_without_assignee") or []
        if stale:
            print(
                f"\nWARN: {len(stale)} high/critical item(s) without assignee",
                file=sys.stderr,
            )
            for item in stale[:5]:
                print(f"  - [{item.get('kind')}] {item.get('title')}", file=sys.stderr)
        return 0
    finally:
        pg.close()


if __name__ == "__main__":
    raise SystemExit(main())
