#!/usr/bin/env python3
"""Collapse duplicate corpus/corrections rows into deduplicated counter records.

Hook-written rows (pre_tool_block, prompt_submit_hook) were uuid-keyed, one per
event — 768 rows by 2026-06-12, 158 of them a single identical sentence.
This merges each unique (source, content) into one record keyed by
correction_record_id() with count/first/last timestamps, and archives the
originals to corpus/corrections-archive (nothing is deleted outright).

Curated rows (source = feedback_*.md files) are left untouched.

Usage:
    python3 scripts/prune_corrections.py            # dry run, prints plan
    python3 scripts/prune_corrections.py --apply    # perform the merge
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.willow_store import WillowStore  # noqa: E402
from willow.fylgja.corrections import COLLECTION, correction_record_id  # noqa: E402

ARCHIVE = "corpus/corrections-archive"
HOOK_SOURCES = {"pre_tool_block", "prompt_submit_hook"}


def plan(store: WillowStore) -> tuple[dict, list]:
    """Group hook-written rows by (source, content). Returns (groups, untouched)."""
    rows = store.all(COLLECTION) or []
    groups: dict[tuple[str, str], list[dict]] = {}
    untouched = []
    for row in rows:
        source = row.get("source", "")
        content = (row.get("content") or "").strip()[:300]
        if source not in HOOK_SOURCES or not content:
            untouched.append(row)
            continue
        groups.setdefault((source, content), []).append(row)
    return groups, untouched


def apply_plan(store: WillowStore, groups: dict) -> tuple[int, int]:
    merged, archived = 0, 0
    for (source, content), rows in groups.items():
        rows.sort(key=lambda r: r.get("created_at", ""))
        canonical_id = correction_record_id(source, content)
        canonical = dict(rows[0])
        canonical["id"] = canonical_id
        canonical["count"] = sum(int(r.get("count", 1)) for r in rows)
        canonical["created_at"] = rows[0].get("created_at", "")
        canonical["last_seen"] = rows[-1].get("created_at", "")
        canonical["content"] = content
        store.put(COLLECTION, canonical, record_id=canonical_id)
        merged += 1
        for row in rows:
            old_id = row.get("id") or row.get("_soil_id")
            if not old_id or old_id == canonical_id:
                continue
            store.put(ARCHIVE, {**row, "archived_from": COLLECTION}, record_id=old_id)
            store.delete(COLLECTION, old_id)
            archived += 1
    return merged, archived


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform the merge")
    args = parser.parse_args()

    store = WillowStore()
    groups, untouched = plan(store)
    total_rows = sum(len(v) for v in groups.values())
    print(f"hook-written rows: {total_rows} in {len(groups)} unique groups")
    print(f"curated rows untouched: {len(untouched)}")
    top = sorted(groups.items(), key=lambda kv: -len(kv[1]))[:5]
    for (source, content), rows in top:
        print(f"  {len(rows):4d}x [{source}] {content[:80]}")

    if not args.apply:
        print("\ndry run — pass --apply to merge and archive")
        return 0

    merged, archived = apply_plan(store, groups)
    remaining = len(store.all(COLLECTION) or [])
    print(f"\nmerged into {merged} canonical records; archived {archived} rows to {ARCHIVE}")
    print(f"{COLLECTION} now holds {remaining} records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
