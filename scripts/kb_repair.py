#!/usr/bin/env python3
"""kb_repair.py — safe KB repair runner (dry-run by default).

Subcommands:
  dedup-title       Disambiguate duplicate active titles (non-lossy rename)
  dedup-exact       Merge exact same-content duplicates (invalidate older)
  delete-dangling   Remove edges with missing/invalid endpoints
  anchor-low-degree Bridge low-degree atoms to a repair anchor

All write subcommands require --apply. Edge writes also require --consent
or WILLOW_HUMAN_CONSENT=1.
"""
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

import core.embedder as emb  # noqa: E402
import core.pg_bridge as pb  # noqa: E402
from core.kb_repair import (  # noqa: E402
    repair_anchor_low_degree,
    repair_dedup_exact,
    repair_dedup_title,
    repair_delete_dangling,
)
from core.pg_bridge import PgBridge, run_migrations  # noqa: E402

emb.embed = lambda text: None  # noqa: E731
pb.embed = emb.embed


def _pg() -> PgBridge:
    pg = PgBridge()
    run_migrations(pg.conn)
    return pg


def cmd_delete_dangling(args: argparse.Namespace) -> int:
    pg = _pg()
    try:
        result = repair_delete_dangling(pg.conn, apply=args.apply)
        print(json.dumps(result, indent=2))
        return 0
    finally:
        pg.close()


def cmd_dedup_exact(args: argparse.Namespace) -> int:
    pg = _pg()
    try:
        result = repair_dedup_exact(
            pg.conn,
            pg,
            apply=args.apply,
            human_consent=args.consent,
        )
        print(json.dumps(result, indent=2))
        if result.get("requires_consent"):
            print("ERROR: --apply requires --consent or WILLOW_HUMAN_CONSENT=1", file=sys.stderr)
            return 1
        return 0
    finally:
        pg.close()


def cmd_dedup_title(args: argparse.Namespace) -> int:
    pg = _pg()
    try:
        result = repair_dedup_title(pg.conn, apply=args.apply)
        print(json.dumps(result, indent=2))
        return 0
    finally:
        pg.close()


def cmd_anchor_low_degree(args: argparse.Namespace) -> int:
    pg = _pg()
    try:
        result = repair_anchor_low_degree(
            pg.conn,
            pg,
            apply=args.apply,
            human_consent=args.consent,
            max_degree=args.max_degree,
            limit=args.limit,
        )
        print(json.dumps(result, indent=2))
        if result.get("requires_consent"):
            print("ERROR: --apply requires --consent or WILLOW_HUMAN_CONSENT=1", file=sys.stderr)
            return 1
        return 0
    finally:
        pg.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="KB repair runner (dry-run by default)")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, func in (
        ("delete-dangling", cmd_delete_dangling),
        ("dedup-exact", cmd_dedup_exact),
        ("dedup-title", cmd_dedup_title),
        ("anchor-low-degree", cmd_anchor_low_degree),
    ):
        p = sub.add_parser(name)
        p.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
        if name in {"dedup-exact", "anchor-low-degree"}:
            p.add_argument(
                "--consent",
                action="store_true",
                help="Operator consent for edge writes (or WILLOW_HUMAN_CONSENT=1)",
            )
        if name == "anchor-low-degree":
            p.add_argument("--max-degree", type=int, default=1)
            p.add_argument("--limit", type=int, default=20)
        p.set_defaults(func=func)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
