#!/usr/bin/env python3
"""
signal_archive_pass.py — TTL cleanup for SOIL signal collections.

Archives signal records that are no longer actionable:
  - Promoted records older than PROMOTED_TTL_DAYS: already lifted to KB;
    the SOIL copy is noise that inflates collection sizes.
  - Unpromoted records older than UNPROMOTED_STALE_TTL_DAYS with
    count < MIN_COUNT_FOR_RETENTION: never met promotion threshold and
    too old to accumulate further signal.

"Archive" = set archived=True + archived_at timestamp. Records are NOT
deleted — they remain queryable for audit, recurrence analysis, and
absorption metrics. The existing promote_signals._load_signals() already
filters promoted records; adding archived=True also hides them from that
loader without removing history.

Usage:
    python3 scripts/signal_archive_pass.py [--dry-run] [--type TYPE]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from scripts.promote_signals import SIGNAL_CONFIGS

PROMOTED_TTL_DAYS: int = 90        # keep promoted SOIL records this long after promotion
UNPROMOTED_STALE_TTL_DAYS: int = 30  # archive unpromoted low-count records after this long
MIN_COUNT_FOR_RETENTION: int = 2   # unpromoted records with count >= this are kept longer


def _parse_dt(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _should_archive_promoted(record: dict, now: datetime) -> bool:
    promoted_at = _parse_dt(record.get("promoted_at"))
    if promoted_at is None:
        return False
    return (now - promoted_at).days >= PROMOTED_TTL_DAYS


def _should_archive_unpromoted(record: dict, now: datetime) -> bool:
    count = int(record.get("count", 1))
    if count >= MIN_COUNT_FOR_RETENTION:
        return False
    created_at = _parse_dt(record.get("created_at"))
    if created_at is None:
        return False
    return (now - created_at).days >= UNPROMOTED_STALE_TTL_DAYS


def _archive_type(
    sig_type: str,
    cfg,
    dry_run: bool,
    now: datetime,
) -> tuple[int, int]:
    """Archive one signal type. Returns (promoted_archived, stale_archived)."""
    try:
        from core.store_port import get_store_port
        store = get_store_port()
    except Exception as e:
        print(f"[archive:{sig_type}] store unavailable: {e}", file=sys.stderr)
        return 0, 0

    records = store.list(cfg.collection) or []
    active = [r for r in records if not r.get("archived")]

    promoted_archived = stale_archived = 0

    for rec in active:
        rec_id = rec.get("id", "")
        is_promoted = bool(rec.get("promoted"))

        if is_promoted and _should_archive_promoted(rec, now):
            if dry_run:
                print(f"  [dry-run] archive promoted {rec_id[:12]} ({sig_type}) promoted_at={rec.get('promoted_at', '')[:10]}")
            else:
                rec["archived"] = True
                rec["archived_at"] = now.isoformat()
                rec["archive_reason"] = "promoted_ttl"
                store.update(cfg.collection, rec_id, rec)
            promoted_archived += 1

        elif not is_promoted and _should_archive_unpromoted(rec, now):
            if dry_run:
                print(f"  [dry-run] archive stale {rec_id[:12]} ({sig_type}) count={rec.get('count', 1)} created={rec.get('created_at', '')[:10]}")
            else:
                rec["archived"] = True
                rec["archived_at"] = now.isoformat()
                rec["archive_reason"] = "stale_unpromoted"
                store.update(cfg.collection, rec_id, rec)
            stale_archived += 1

    if promoted_archived or stale_archived:
        print(f"[archive:{sig_type}] promoted={promoted_archived} stale={stale_archived}")

    return promoted_archived, stale_archived


def archive_pass(dry_run: bool = False, signal_type_filter: str | None = None) -> dict:
    """Run archive pass for all (or one) signal types. Returns summary dict."""
    now = datetime.now(timezone.utc)
    types_to_run = (
        {signal_type_filter: SIGNAL_CONFIGS[signal_type_filter]}
        if signal_type_filter
        else dict(SIGNAL_CONFIGS)
    )

    total_promoted = total_stale = 0
    by_type: dict[str, dict] = {}

    for sig_type, cfg in types_to_run.items():
        p, s = _archive_type(sig_type, cfg, dry_run, now)
        by_type[sig_type] = {"promoted_archived": p, "stale_archived": s}
        total_promoted += p
        total_stale += s

    total = total_promoted + total_stale
    print(f"[archive] done — promoted_archived={total_promoted} stale_archived={total_stale} total={total}")
    return {
        "total_archived": total,
        "promoted_archived": total_promoted,
        "stale_archived": total_stale,
        "by_type": by_type,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive stale SOIL signal records")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--type", dest="signal_type", choices=list(SIGNAL_CONFIGS.keys()),
        help="Archive only this signal type (default: all)",
    )
    args = parser.parse_args()
    archive_pass(dry_run=args.dry_run, signal_type_filter=args.signal_type)


if __name__ == "__main__":
    main()
