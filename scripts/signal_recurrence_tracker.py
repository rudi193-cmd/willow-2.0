#!/usr/bin/env python3
"""
signal_recurrence_tracker.py — measure whether promoted corrections are absorbed.

For each promoted SOIL signal (promoted=True), scans unpromoted records in the
same collection for content-key matches. A match means the same correction/
scope_redirect/tool_denial fired again after it was already promoted to KB —
the behavioral change did not land.

On detection:
  - Increments `recurrence_count` on the promoted SOIL record.
  - Marks the new record `recurrence_counted=True` to prevent double-counting
    across norn passes.
  - When `recurrence_count >= RECURRENCE_THRESHOLD` and valence is negative,
    raises a flag in `hanuman/flags` so it surfaces at boot.

Positive-valence signals (confirmations) that recur are recorded but do not
raise flags — recurrence is desirable reinforcement.

Usage:
    python3 scripts/signal_recurrence_tracker.py [--dry-run] [--type TYPE]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from core.agent_identity import require_agent_name

AGENT = require_agent_name()

RECURRENCE_THRESHOLD = 3  # flag fires at this many post-promotion recurrences

# Import shared structures from promote_signals
from scripts.promote_signals import SIGNAL_CONFIGS, _normalize


def _content_key(record: dict, signal_type: str) -> str:
    """Stable match key — mirrors promote_signals._content_key."""
    if signal_type == "tool_denial":
        tool = record.get("tool_name", "").lower()
        reason = _normalize(record.get("reason", ""))
        return f"{tool}|{reason[:100]}"
    return _normalize(record.get("content", ""))


def _load_collection(collection: str) -> list[dict]:
    try:
        from core.store_port import get_store_port
        store = get_store_port()
        return store.list(collection) or []
    except Exception as e:
        print(f"[recurrence] failed to load {collection}: {e}", file=sys.stderr)
        return []


def _flag_exists(flag_id: str) -> bool:
    try:
        from core.store_port import get_store_port
        store = get_store_port()
        rec = store.get("hanuman/flags", flag_id)
        return rec is not None
    except Exception:
        return False


def _raise_flag(
    flag_id: str,
    sig_type: str,
    content_preview: str,
    recurrence_count: int,
    dry_run: bool,
) -> bool:
    if dry_run:
        print(f"  [dry-run] would raise flag {flag_id} ({sig_type} recurred {recurrence_count}x)")
        return True
    try:
        from core.store_port import get_store_port
        store = get_store_port()
        store.put("hanuman/flags", flag_id, {
            "id": flag_id,
            "flag_state": "open",
            "title": f"{sig_type} recurring after promotion ({recurrence_count}x): {content_preview[:60]}",
            "description": (
                f"A promoted {sig_type} atom has recurred {recurrence_count} times after promotion. "
                "The behavioral change is not being absorbed. Review the KB atom and consider "
                "whether the correction needs to be strengthened, moved to a higher-visibility "
                "location, or the root cause addressed in the codebase."
            ),
            "fix_path": f"kb_search(query='{content_preview[:50]}', category='{sig_type}') — review + strengthen atom",
            "priority": "high" if recurrence_count >= RECURRENCE_THRESHOLD * 2 else "medium",
            "signal_type": sig_type,
            "recurrence_count": recurrence_count,
            "created": datetime.now(timezone.utc).isoformat(),
            "noted_by": AGENT,
        })
        return True
    except Exception as e:
        print(f"[recurrence] failed to raise flag {flag_id}: {e}", file=sys.stderr)
        return False


def _check_type(
    sig_type: str,
    cfg,
    dry_run: bool,
) -> tuple[int, int]:
    """Check one signal type. Returns (recurrences_found, flags_raised)."""
    records = _load_collection(cfg.collection)
    if not records:
        return 0, 0

    promoted = [r for r in records if r.get("promoted")]
    unpromoted = [r for r in records if not r.get("promoted") and not r.get("recurrence_counted")]

    if not promoted or not unpromoted:
        return 0, 0

    # Build index: content_key → promoted record
    promoted_index: dict[str, dict] = {}
    for rec in promoted:
        key = _content_key(rec, sig_type)
        if key:
            promoted_index[key] = rec

    recurrences = 0
    flags_raised = 0
    now = datetime.now(timezone.utc).isoformat()

    try:
        from core.store_port import get_store_port
        store = get_store_port()
    except Exception as e:
        print(f"[recurrence] store unavailable: {e}", file=sys.stderr)
        return 0, 0

    for new_rec in unpromoted:
        key = _content_key(new_rec, sig_type)
        if not key or key not in promoted_index:
            continue

        promoted_rec = promoted_index[key]
        recurrences += 1
        promoted_rec_id = promoted_rec.get("id", "")
        new_rec_id = new_rec.get("id", "")

        # Update promoted record
        promoted_rec["recurrence_count"] = promoted_rec.get("recurrence_count", 0) + 1
        recurrence_ids = promoted_rec.get("recurrence_ids", [])
        if new_rec_id not in recurrence_ids:
            recurrence_ids.append(new_rec_id)
        promoted_rec["recurrence_ids"] = recurrence_ids

        if not dry_run:
            store.update(cfg.collection, promoted_rec_id, promoted_rec)
            # Mark new record as counted so it doesn't re-trigger next pass
            new_rec["recurrence_counted"] = True
            new_rec["recurrence_counted_at"] = now
            store.update(cfg.collection, new_rec_id, new_rec)

        direction = "↑" if cfg.valence == "positive" else "!"
        content_preview = (new_rec.get("content") or new_rec.get("reason") or "")[:60]
        count = promoted_rec["recurrence_count"]
        print(
            f"  [{sig_type}] recurrence {direction} count={count} "
            f"promoted_id={promoted_rec_id[:12]} | {content_preview}"
        )

        # Raise flag for negative-valence signals at threshold
        if cfg.valence == "negative" and count >= RECURRENCE_THRESHOLD:
            flag_id = f"recurrence-{sig_type}-{promoted_rec_id[:12]}"
            if not _flag_exists(flag_id):
                content_preview_full = (promoted_rec.get("content") or promoted_rec.get("reason") or "")[:80]
                raised = _raise_flag(flag_id, sig_type, content_preview_full, count, dry_run)
                if raised:
                    flags_raised += 1

    return recurrences, flags_raised


def track_recurrence(dry_run: bool = False, signal_type_filter: str | None = None) -> dict:
    """Run recurrence check for all (or one) signal types. Returns summary dict."""
    types_to_check = (
        {signal_type_filter: SIGNAL_CONFIGS[signal_type_filter]}
        if signal_type_filter
        else dict(SIGNAL_CONFIGS)
    )

    total_recurrences = 0
    total_flags = 0
    by_type: dict[str, dict] = {}

    for sig_type, cfg in types_to_check.items():
        r, f = _check_type(sig_type, cfg, dry_run)
        by_type[sig_type] = {"recurrences": r, "flags_raised": f}
        total_recurrences += r
        total_flags += f
        if r:
            print(f"[recurrence:{sig_type}] recurrences={r} flags={f}")

    print(f"[recurrence] done — total_recurrences={total_recurrences} flags_raised={total_flags}")
    return {
        "total_recurrences": total_recurrences,
        "flags_raised": total_flags,
        "by_type": by_type,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Track signal recurrence post-promotion")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--type", dest="signal_type", choices=list(SIGNAL_CONFIGS.keys()),
        help="Check only this signal type (default: all)",
    )
    args = parser.parse_args()
    track_recurrence(dry_run=args.dry_run, signal_type_filter=args.signal_type)


if __name__ == "__main__":
    main()
