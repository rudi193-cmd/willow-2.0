#!/usr/bin/env python3
"""
archive_block_flags.py — block-telemetry flag lifecycle in willow/flags.

(c) Archive resolved flags silent for >N days (flag_state=archived).
(d) Retire pre-#436 open flags whose titles claimed "Blessed path … broken"
    — superseded by "Repeated enforcement" telemetry (#436).

Usage:
    python3 scripts/archive_block_flags.py [--dry-run] [--days N]
    python3 scripts/archive_block_flags.py --retire-legacy [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_ARCHIVE_AFTER_DAYS = 7
LEGACY_BLOCK_TITLE_PREFIX = "Blessed path"
LEGACY_ARCHIVE_REASON = (
    "pre-#436 taxonomy ('Blessed path') superseded by repeated-enforcement flags"
)


def _flag_id(flag: dict) -> str | None:
    return flag.get("id") or flag.get("_soil_id")


def is_legacy_block_flag(flag: dict) -> bool:
    """Pre-#436 block_telemetry titles implied routing was broken, not repetitive."""
    if flag.get("source") != "block_telemetry":
        return False
    title = str(flag.get("title") or "")
    return title.startswith(LEGACY_BLOCK_TITLE_PREFIX)


def retire_legacy_block_flags(dry_run: bool = False) -> int:
    """Archive open legacy block_telemetry flags. Returns count retired."""
    try:
        store = _load_store()
        all_flags = store.all("willow/flags") or []
    except Exception as e:
        print(f"[archive_block_flags] store unavailable: {e}", file=sys.stderr)
        return 0

    retired = 0
    now = datetime.now(timezone.utc).isoformat()
    for flag in all_flags:
        if flag.get("flag_state") != "open" or not is_legacy_block_flag(flag):
            continue
        flag_id = _flag_id(flag)
        if not flag_id:
            continue
        if dry_run:
            retired += 1
            continue
        try:
            updated = dict(flag)
            updated["flag_state"] = "archived"
            updated["archived_at"] = now
            updated["archived_reason"] = LEGACY_ARCHIVE_REASON
            store.put("willow/flags", updated, record_id=flag_id)
            retired += 1
        except Exception as e:
            print(f"[archive_block_flags] {flag_id}: {e}", file=sys.stderr)
    return retired


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


def archive_pass(dry_run: bool = False, days: int = DEFAULT_ARCHIVE_AFTER_DAYS) -> int:
    """Archive resolved block telemetry flags silent for >days. Returns count archived.

    Callable by norn_pass or manually. Skips flags whose rule is still firing
    recently — part (b) will reopen them on the next threshold crossing.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    archived = 0

    try:
        store = _load_store()
        all_flags = store.all("willow/flags") or []
    except Exception as e:
        print(f"[archive_block_flags] store unavailable: {e}", file=sys.stderr)
        return 0

    resolved = [
        f for f in all_flags
        if f.get("source") == "block_telemetry" and f.get("flag_state") == "resolved"
    ]

    for flag in resolved:
        rule_key = flag.get("rule_key")
        flag_id = _flag_id(flag)
        if not rule_key or not flag_id:
            continue

        telemetry = store.get("corpus/block_telemetry", rule_key) or {}
        last_seen_dt = _parse_dt(telemetry.get("last_seen"))

        if last_seen_dt and last_seen_dt > cutoff:
            continue

        if dry_run:
            archived += 1
            continue

        try:
            last_seen_str = last_seen_dt.date().isoformat() if last_seen_dt else "never"
            updated = dict(flag)
            updated["flag_state"] = "archived"
            updated["archived_at"] = datetime.now(timezone.utc).isoformat()
            updated["archived_reason"] = f"rule silent for >{days}d (last_seen={last_seen_str})"
            store.put("willow/flags", updated, record_id=flag_id)
            archived += 1
        except Exception as e:
            print(f"[archive_block_flags] {flag_id}: {e}", file=sys.stderr)

    return archived


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive block telemetry flags in willow/flags")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--retire-legacy",
        action="store_true",
        help="Archive open pre-#436 'Blessed path' block_telemetry flags",
    )
    parser.add_argument("--days", type=int, default=DEFAULT_ARCHIVE_AFTER_DAYS,
                        help=f"Archive resolved flags silent for this many days (default: {DEFAULT_ARCHIVE_AFTER_DAYS})")
    args = parser.parse_args()

    if args.retire_legacy:
        count = retire_legacy_block_flags(dry_run=args.dry_run)
        label = "would retire" if args.dry_run else "retired"
        print(f"[archive] legacy block flags — {label}={count}")
        return

    try:
        store = _load_store()
        all_flags = store.all("willow/flags") or []
    except Exception as e:
        print(f"[archive] store unavailable: {e}", file=sys.stderr)
        sys.exit(1)

    block_flags = [f for f in all_flags if f.get("source") == "block_telemetry"]
    resolved = [f for f in block_flags if f.get("flag_state") == "resolved"]
    legacy_open = [f for f in block_flags if f.get("flag_state") == "open" and is_legacy_block_flag(f)]
    print(
        f"[archive] {len(block_flags)} block flags total, "
        f"{len(resolved)} resolved, {len(legacy_open)} legacy open"
    )

    count = archive_pass(dry_run=args.dry_run, days=args.days)
    label = "would archive" if args.dry_run else "archived"
    print(f"[archive] done — {label}={count}")


if __name__ == "__main__":
    main()
