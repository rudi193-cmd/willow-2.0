#!/usr/bin/env python3
"""split_corrections_telemetry.py — Phase 4(a) backfill.

The pre_tool hook used to write a fresh `corr-` atom to corpus/corrections on
every block; the routing now sends those to corpus/block_telemetry counters
(willow/fylgja/events/pre_tool.py). This script migrates the *existing*
source='pre_tool_block' records out of corpus/corrections — aggregating them
into the per-rule counters and soft-deleting the originals so corpus/corrections
is left as human-feedback-only.

Reversible: soft-delete (WillowStore.delete sets deleted=1, preserved in the
audit_log); on --apply a FRANK ledger 'corrections_split' entry records counts.

Usage:
    python3 scripts/split_corrections_telemetry.py            # dry-run (default)
    python3 scripts/split_corrections_telemetry.py --apply
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from core.willow_store import WillowStore  # noqa: E402

CORR = "corpus/corrections"
TELEM = "corpus/block_telemetry"


def _rule_key(tool_name: str, reason: str) -> str:
    """Must match willow/fylgja/events/pre_tool.py::_rule_key exactly."""
    digest = hashlib.sha1(f"{tool_name}|{reason[:80]}".encode("utf-8")).hexdigest()[:8]
    return f"block-{digest}"


def _parse_block(content: str) -> tuple[str, str]:
    """'Blocked <tool>: <reason>' → (tool, reason). Falls back gracefully."""
    body = content[len("Blocked "):] if content.startswith("Blocked ") else content
    tool, sep, reason = body.partition(": ")
    return (tool.strip(), reason.strip()) if sep else ("unknown", body.strip())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Migrate pre_tool_block corrections into telemetry counters")
    ap.add_argument("--apply", action="store_true", help="perform the migration (default: dry-run)")
    args = ap.parse_args(argv)

    store = WillowStore()
    rows = store.list(CORR) or []
    blocks = [r for r in rows if r.get("source") == "pre_tool_block"]
    human = len(rows) - len(blocks)

    # Aggregate into counters keyed exactly like the live hook.
    counters: dict[str, dict] = {}
    for r in blocks:
        tool, reason = _parse_block(r.get("content", ""))
        key = _rule_key(tool, reason)
        c = counters.setdefault(key, {"tool": tool, "sample_reason": reason[:200],
                                      "hit_count": 0, "ids": []})
        c["hit_count"] += 1
        c["ids"].append(r.get("id") or r.get("_id") or r.get("_soil_id"))

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[corrections-split {mode}]")
    print(f"  corpus/corrections rows : {len(rows)} ({human} human-feedback, {len(blocks)} block-spam)")
    print(f"  → {len(counters)} rule counters in corpus/block_telemetry; "
          f"{len(blocks)} block records soft-deleted")
    for key, c in sorted(counters.items(), key=lambda kv: -kv[1]["hit_count"])[:10]:
        print(f"    {key}  x{c['hit_count']:<4} {c['tool']}: {c['sample_reason'][:50]}")

    if not args.apply:
        print(f"{mode}: re-run with --apply to migrate")
        return 0
    if not blocks:
        print("APPLY: nothing to migrate")
        return 0

    # Merge counters with any existing live telemetry, then soft-delete originals.
    deleted = 0
    for key, c in counters.items():
        existing = store.get(TELEM, key) or {}
        store.put(TELEM, {
            "id": key,
            "type": "block_telemetry",
            "tool": c["tool"],
            "sample_reason": c["sample_reason"],
            "hit_count": int(existing.get("hit_count") or 0) + c["hit_count"],
            "first_seen": existing.get("first_seen"),
            "last_seen": existing.get("last_seen"),
            "backfilled": True,
            "b17": "BTEL0",
        }, record_id=key)
        for rid in c["ids"]:
            if rid and store.delete(CORR, rid):
                deleted += 1

    print(f"APPLY: {len(counters)} counters written; {deleted} block records soft-deleted from {CORR}")

    try:
        from core.pg_bridge import PgBridge
        PgBridge().ledger_append("willow", "corrections_split", {
            "summary": (f"Phase 4(a): migrated {deleted} pre_tool_block records from "
                        f"corpus/corrections into {len(counters)} block_telemetry counters. "
                        f"{human} human-feedback corrections untouched."),
            "block_records_migrated": deleted,
            "rule_counters": len(counters),
            "human_feedback_kept": human,
        })
        print("APPLY: recorded in FRANK ledger (corrections_split)")
    except Exception as e:
        print(f"APPLY: WARNING — ledger record failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
