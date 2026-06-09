#!/usr/bin/env python3
"""human_attestation.py — operator CLI for durable human attestations."""
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

from core.human_attestation import SUBJECT_TYPES, STATUSES, create, list_records
from core.pg_bridge import PgBridge, run_migrations


def _pg() -> PgBridge:
    pg = PgBridge()
    run_migrations(pg.conn)
    return pg


def cmd_create(args: argparse.Namespace) -> int:
    pg = _pg()
    try:
        result = create(
            pg.conn,
            subject_id=args.subject_id,
            subject_type=args.subject_type,
            status=args.status,
            attested_by=args.by,
            agent=args.agent,
            statement=args.statement,
            evidence_ref=args.evidence_ref,
        )
        print(json.dumps(result, indent=2))
        return 0
    finally:
        pg.close()


def cmd_list(args: argparse.Namespace) -> int:
    pg = _pg()
    try:
        rows = list_records(
            pg.conn,
            subject_id=args.subject_id,
            subject_type=args.subject_type,
            status=args.status,
            limit=args.limit,
        )
        print(json.dumps({"items": rows, "count": len(rows)}, indent=2))
        return 0
    finally:
        pg.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Human attestation CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Create an attestation record")
    p_create.add_argument("subject_id")
    p_create.add_argument("--subject-type", default="knowledge_atom", choices=SUBJECT_TYPES)
    p_create.add_argument("--status", default="attested", choices=STATUSES)
    p_create.add_argument("--by", default="operator")
    p_create.add_argument("--agent", default="")
    p_create.add_argument("--statement", default="")
    p_create.add_argument("--evidence-ref", default="")
    p_create.set_defaults(func=cmd_create)

    p_list = sub.add_parser("list", help="List attestation records")
    p_list.add_argument("--subject-id", default="")
    p_list.add_argument("--subject-type", default="", choices=[""] + list(SUBJECT_TYPES))
    p_list.add_argument("--status", default="", choices=[""] + list(STATUSES))
    p_list.add_argument("--limit", type=int, default=50)
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
