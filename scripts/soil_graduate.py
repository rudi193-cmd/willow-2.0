#!/usr/bin/env python3
"""soil_graduate.py — graduate stabilized SOIL records into the intake layer.

Audit PR 6 (operator work order, rev 5): SOIL records that have stopped
changing are working memory that has earned long-term storage. Rather than
ingesting straight into the KB, graduation writes an intake record — the
record then rides the existing norn pass (promote_intake.py) with its tier
routing, quality gates, and bi-temporal supersede semantics intact.

A graduated record is marked (graduated_at + intake record id) in place —
supersede-not-delete; the SOIL record stays readable.

Criteria (all must hold):
- record not updated for --days (default 14)
- collection not in the working-state exclusion list (flags, stack, forks,
  corpus, intake mirrors) — those are operational state, not knowledge
- record not already graduated

Default dry-run; pass --apply to write.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from core import soil
from core.intake import write as intake_write

EXCLUDE_GLOBS = (
    "*/flags", "*/stack", "*/forks/*", "corpus/*", "*/intake*",
    "*/overseer", "*/triage*",
)


def list_collections() -> list[str]:
    root = soil._root()
    return sorted(
        str(db.parent.relative_to(root))
        for db in root.rglob("store.db")
    )


def is_excluded(collection: str) -> bool:
    return any(fnmatch.fnmatch(collection, g) for g in EXCLUDE_GLOBS)


def stable_records(collection: str, cutoff: datetime) -> list[tuple[str, dict, str]]:
    """Yield (record_id, record, updated_at) for ungraduated records older than cutoff."""
    db = soil._root() / collection / "store.db"
    if not db.exists():
        return []
    conn = sqlite3.connect(str(db))
    rows = conn.execute(
        "SELECT id, data, updated_at FROM records WHERE deleted=0"
    ).fetchall()
    conn.close()
    out = []
    for rid, data, updated_at in rows:
        try:
            rec = json.loads(data)
        except (TypeError, ValueError):
            continue
        if rec.get("graduated_at"):
            continue
        try:
            ts = datetime.fromisoformat(updated_at)
        except (TypeError, ValueError):
            continue
        if ts < cutoff:
            out.append((rid, rec, updated_at))
    return out


def graduate(collection: str, rid: str, rec: dict, agent: str, apply: bool) -> str:
    content = json.dumps({k: v for k, v in rec.items() if not k.startswith("_")},
                         ensure_ascii=False, default=str)
    title = rec.get("title") or rec.get("name") or f"{collection}/{rid}"
    if not apply:
        return "(dry-run)"
    intake_id = intake_write(
        content=content,
        source="soil-graduation",
        agent=agent,
        tier="observed",
        confidence=0.85,
        title=str(title)[:120],
        namespace=collection.split("/")[0],
        extra={"soil_collection": collection, "soil_record_id": rid,
               "category": "soil-graduation"},
    )
    rec["graduated_at"] = datetime.now().isoformat()
    rec["graduated_intake_id"] = intake_id
    soil.put(collection, rid, rec)
    return intake_id


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=14,
                    help="stability window — untouched for this many days (default 14)")
    ap.add_argument("--agent", default="willow", help="intake agent namespace")
    ap.add_argument("--limit", type=int, default=50,
                    help="max records per run (default 50)")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    args = ap.parse_args()

    cutoff = datetime.now() - timedelta(days=args.days)
    total = 0
    for collection in list_collections():
        if is_excluded(collection):
            continue
        for rid, rec, updated_at in stable_records(collection, cutoff):
            if total >= args.limit:
                print(f"[graduate] limit {args.limit} reached — rerun for the rest")
                return 0
            result = graduate(collection, rid, rec, args.agent, args.apply)
            print(f"[graduate] {collection}/{rid} (stable since {updated_at[:10]}) -> {result}")
            total += 1

    mode = "graduated" if args.apply else "would graduate"
    print(f"[graduate] {mode} {total} records (window {args.days}d)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
