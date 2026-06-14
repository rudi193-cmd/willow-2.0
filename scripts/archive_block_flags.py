#!/usr/bin/env python3
"""
archive_block_flags.py — corrections lifecycle part (c): archive silent block flags.

A block telemetry flag (source=block_telemetry in willow/flags) that has been
resolved AND whose rule hasn't fired in ARCHIVE_AFTER_DAYS is archived by setting
flag_state="archived". This prevents resolved flags from cluttering the active
flag list indefinitely.

A flag is NOT archived if its rule is still firing recently — part (b) will
reopen it on the next threshold crossing anyway, so it should stay visible.

Usage:
    python3 scripts/archive_block_flags.py [--dry-run] [--days N]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_ARCHIVE_AFTER_DAYS = 7


def _load_store():
    from core.willow_store import WillowStore
    return WillowStore()


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive silent block telemetry flags")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--days", type=int, default=DEFAULT_ARCHIVE_AFTER_DAYS,
                        help=f"Archive resolved flags silent for this many days (default: {DEFAULT_ARCHIVE_AFTER_DAYS})")
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    try:
        store = _load_store()
    except Exception as e:
        print(f"[archive] store unavailable: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        all_flags = store.all("willow/flags") or []
    except Exception as e:
        print(f"[archive] failed to load willow/flags: {e}", file=sys.stderr)
        sys.exit(1)

    block_flags = [f for f in all_flags if f.get("source") == "block_telemetry"]
    resolved = [f for f in block_flags if f.get("flag_state") == "resolved"]

    print(f"[archive] {len(block_flags)} block flags total, {len(resolved)} resolved")

    archived = skipped_recent = skipped_no_telemetry = 0

    for flag in resolved:
        rule_key = flag.get("rule_key")
        flag_id = flag.get("id") or flag.get("_soil_id")
        if not rule_key or not flag_id:
            continue

        telemetry = store.get("corpus/block_telemetry", rule_key) or {}
        last_seen_dt = _parse_dt(telemetry.get("last_seen"))

        if telemetry and last_seen_dt is None:
            skipped_no_telemetry += 1
            print(f"  [skip] {flag_id} — telemetry row exists but last_seen unparseable")
            continue

        if last_seen_dt and last_seen_dt > cutoff:
            skipped_recent += 1
            hit_count = telemetry.get("hit_count", "?")
            print(f"  [skip] {flag_id} — rule still active (last_seen {last_seen_dt.date()}, {hit_count} hits)")
            continue

        last_seen_str = last_seen_dt.date().isoformat() if last_seen_dt else "never"
        if args.dry_run:
            print(f"  [dry-run] would archive {flag_id} (rule={rule_key}, last_seen={last_seen_str})")
            archived += 1
            continue

        try:
            updated = dict(flag)
            updated["flag_state"] = "archived"
            updated["archived_at"] = datetime.now(timezone.utc).isoformat()
            updated["archived_reason"] = f"rule silent for >{args.days}d (last_seen={last_seen_str})"
            store.put("willow/flags", updated, record_id=flag_id)
            print(f"  [archived] {flag_id} (rule={rule_key}, last_seen={last_seen_str})")
            archived += 1
        except Exception as e:
            print(f"  [error] {flag_id}: {e}", file=sys.stderr)

    print(
        f"[archive] done — archived={archived} "
        f"skipped_recent={skipped_recent} skipped_no_telemetry={skipped_no_telemetry}"
    )


if __name__ == "__main__":
    main()
