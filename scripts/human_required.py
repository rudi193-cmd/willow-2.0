#!/usr/bin/env python3
"""human_required.py — operator CLI for the human-required queue."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    ps = str(p)
    if ps not in sys.path:
        sys.path.insert(0, ps)

from core.human_required import KINDS, STATUSES, enqueue, list_items, resolve, seed_defaults, stats
from core.pg_bridge import PgBridge, run_migrations


def _pg() -> PgBridge:
    pg = PgBridge()
    run_migrations(pg.conn)
    return pg


def cmd_list(args: argparse.Namespace) -> int:
    pg = _pg()
    try:
        payload = {
            "stats": stats(pg.conn),
            "items": list_items(pg.conn, status=args.status, kind=args.kind, limit=args.limit),
        }
        print(json.dumps(payload, indent=2))
        return 0
    finally:
        pg.close()


def cmd_enqueue(args: argparse.Namespace) -> int:
    pg = _pg()
    try:
        result = enqueue(
            pg.conn,
            kind=args.kind,
            title=args.title,
            summary=args.summary,
            priority=args.priority,
            source_agent=args.agent,
            source_ref=args.source_ref,
            assignee=args.assignee,
        )
        print(json.dumps(result, indent=2))
        return 0 if "error" not in result else 1
    finally:
        pg.close()


def cmd_resolve(args: argparse.Namespace) -> int:
    pg = _pg()
    try:
        result = resolve(
            pg.conn,
            args.id,
            resolved_by=args.by,
            status=args.status,
            note=args.note,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("updated") else 1
    finally:
        pg.close()


def cmd_seed(_args: argparse.Namespace) -> int:
    pg = _pg()
    try:
        result = seed_defaults(pg.conn)
        print(json.dumps(result, indent=2))
        return 0
    finally:
        pg.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Human-required queue operator CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List queue items")
    p_list.add_argument("--status", default="open", choices=STATUSES)
    p_list.add_argument("--kind", default="", choices=[""] + list(KINDS))
    p_list.add_argument("--limit", type=int, default=50)
    p_list.set_defaults(func=cmd_list)

    p_enqueue = sub.add_parser("enqueue", help="Enqueue a human-required item")
    p_enqueue.add_argument("--kind", required=True, choices=KINDS)
    p_enqueue.add_argument("--title", required=True)
    p_enqueue.add_argument("--summary", default="")
    p_enqueue.add_argument("--priority", default="normal", choices=("low", "normal", "high", "critical"))
    p_enqueue.add_argument("--agent", default="operator")
    p_enqueue.add_argument("--source-ref", default="")
    p_enqueue.add_argument("--assignee", default="")
    p_enqueue.set_defaults(func=cmd_enqueue)

    p_resolve = sub.add_parser("resolve", help="Resolve/acknowledge/dismiss an item")
    p_resolve.add_argument("id")
    p_resolve.add_argument("--by", default="operator")
    p_resolve.add_argument("--status", default="resolved", choices=("resolved", "dismissed", "acknowledged"))
    p_resolve.add_argument("--note", default="")
    p_resolve.set_defaults(func=cmd_resolve)

    p_seed = sub.add_parser("seed", help="Seed known human-gap items")
    p_seed.set_defaults(func=cmd_seed)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
