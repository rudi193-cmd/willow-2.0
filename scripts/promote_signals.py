#!/usr/bin/env python3
"""
promote_signals.py — norn-pass: promote recurring behavioral signals to knowledge table.

Reads all five signal collections from WillowStore and promotes recurring signals
to KB atoms with a valence field and time-decay weighting. Raw count alone is a
weak signal — a correction issued yesterday should outweigh the same correction
from two months ago with the same count. Time-weighted count (count × e^(-λ·days))
solves this.

Collections handled:
  corpus/corrections     → category=correction,    valence=negative, min_count=2
  corpus/preferences     → category=preference,    valence=neutral,  min_count=2
  corpus/confirmations   → category=confirmation,  valence=positive, min_count=3
  corpus/scope_redirects → category=scope_redirect,valence=negative, min_count=2
  corpus/tool_denials    → category=tool_denial,   valence=negative, min_count=3

Usage:
    python3 scripts/promote_signals.py [--dry-run] [--min-count N] [--type TYPE]
    python3 scripts/promote_signals.py --type correction --dry-run
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from core.agent_identity import require_agent_name
from willow.fylgja._mcp import call

AGENT = require_agent_name()

HALF_LIFE_DAYS = 30.0  # signal from 30 days ago counts as 0.5×


class SignalConfig(NamedTuple):
    collection: str
    category: str
    valence: str
    base_confidence: float
    default_min_count: int


SIGNAL_CONFIGS: dict[str, SignalConfig] = {
    "correction": SignalConfig(
        collection="corpus/corrections",
        category="correction",
        valence="negative",
        base_confidence=0.85,
        default_min_count=2,
    ),
    "preference": SignalConfig(
        collection="corpus/preferences",
        category="preference",
        valence="neutral",
        base_confidence=0.75,
        default_min_count=2,
    ),
    "confirmation": SignalConfig(
        collection="corpus/confirmations",
        category="confirmation",
        valence="positive",
        base_confidence=0.70,
        default_min_count=3,
    ),
    "scope_redirect": SignalConfig(
        collection="corpus/scope_redirects",
        category="scope_redirect",
        valence="negative",
        base_confidence=0.65,
        default_min_count=2,
    ),
    "tool_denial": SignalConfig(
        collection="corpus/tool_denials",
        category="tool_denial",
        valence="negative",
        base_confidence=0.80,
        default_min_count=3,
    ),
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())[:200]


def _time_decay(last_seen_iso: str) -> float:
    """Exponential decay: signal from HALF_LIFE_DAYS ago counts as 0.5×."""
    try:
        last = datetime.fromisoformat(last_seen_iso)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days = max(0.0, (now - last).total_seconds() / 86400)
        return math.exp(-math.log(2) * days / HALF_LIFE_DAYS)
    except Exception:
        return 1.0


def _weighted_count(record: dict) -> float:
    """time-decay × raw count."""
    count = int(record.get("count", 1))
    last_seen = record.get("last_seen") or record.get("created_at", "")
    return count * _time_decay(last_seen)


def _load_signals(collection: str) -> list[dict]:
    try:
        from core.willow_store import WillowStore
        store = WillowStore()
        return store.all(collection) or []
    except Exception as e:
        print(f"[promote] failed to load {collection}: {e}", file=sys.stderr)
        return []


def _mark_promoted(collection: str, record_ids: list[str]) -> None:
    try:
        from core.willow_store import WillowStore
        store = WillowStore()
        now = datetime.now(timezone.utc).isoformat()
        for rid in record_ids:
            rec = store.get(collection, rid)
            if rec:
                rec["promoted"] = True
                rec["promoted_at"] = now
                store.update(collection, rid, rec)
    except Exception as e:
        print(f"[promote] mark promoted failed: {e}", file=sys.stderr)


def _content_key(record: dict, signal_type: str) -> str:
    """Stable grouping key for dedup across signal types."""
    if signal_type == "tool_denial":
        tool = record.get("tool_name", "")
        reason = _normalize(record.get("reason", ""))
        return f"{tool}|{reason[:100]}"
    return _normalize(record.get("content", ""))


def promote_signal_type(
    signal_type: str,
    cfg: SignalConfig,
    min_count: int,
    dry_run: bool,
) -> tuple[int, int]:
    """Promote one signal type. Returns (promoted, skipped)."""
    records = _load_signals(cfg.collection)
    if not records:
        print(f"[promote:{signal_type}] no records")
        return 0, 0

    pending = [r for r in records if not r.get("promoted")]
    print(f"[promote:{signal_type}] {len(records)} total, {len(pending)} pending")

    # Group by normalized content
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in pending:
        key = _content_key(r, signal_type)
        if key:
            groups[key].append(r)

    promoted = skipped = 0
    for norm_key, group_records in sorted(
        groups.items(),
        key=lambda x: -sum(_weighted_count(r) for r in x[1]),
    ):
        total_weighted = sum(_weighted_count(r) for r in group_records)
        raw_count = sum(int(r.get("count", 1)) for r in group_records)

        if total_weighted < min_count * 0.5:
            skipped += 1
            continue

        sessions = list({r.get("session_id", "")[:8] for r in group_records if r.get("session_id")})
        canonical = group_records[0].get("content", norm_key)[:300]
        if signal_type == "tool_denial":
            tool_name = group_records[0].get("tool_name", "?")
            canonical = f"Blocked {tool_name}: {group_records[0].get('reason', '')[:200]}"

        # Confidence: base + time-weighted bonus (capped at base+0.15)
        bonus = min(total_weighted * 0.03, 0.15)
        confidence = round(cfg.base_confidence + bonus, 3)

        title = f"{cfg.category}: {canonical[:60]}"
        tags = [
            cfg.category,
            f"valence:{cfg.valence}",
            AGENT,
            f"count:{raw_count}",
            f"weighted:{total_weighted:.1f}",
        ]
        keywords = [w for w in norm_key.split() if len(w) > 4][:8]

        if dry_run:
            print(
                f"  [dry-run] {title[:70]}\n"
                f"    raw={raw_count} weighted={total_weighted:.1f} "
                f"conf={confidence} sessions={sessions[:3]}"
            )
            promoted += 1
            continue

        try:
            result = call("kb_ingest", {
                "app_id":      AGENT,
                "title":       title,
                "summary":     canonical,
                "source_type": "norn_pass",
                "source_id":   f"{cfg.category}:{raw_count}",
                "category":    cfg.category,
                "keywords":    keywords,
                "tags":        tags,
                "tier":        "observed",
                "confidence":  confidence,
            }, timeout=15)
            if result.get("blocked"):
                print(f"  [blocked] {title[:60]} — {result.get('flags')}")
            else:
                atom_id = result.get("id", "?")
                print(
                    f"  [promoted] {atom_id} raw={raw_count} "
                    f"weighted={total_weighted:.1f} conf={confidence}: {canonical[:60]}"
                )
                _mark_promoted(cfg.collection, [r["id"] for r in group_records if r.get("id")])
                promoted += 1
        except Exception as e:
            print(f"  [error] {e} — {canonical[:60]}", file=sys.stderr)

    print(f"[promote:{signal_type}] done — promoted={promoted} skipped={skipped}")
    return promoted, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote recurring behavioral signals to KB")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--min-count", type=int, default=0,
        help="Override minimum weighted count (0 = use per-type default)"
    )
    parser.add_argument(
        "--type", dest="signal_type", choices=list(SIGNAL_CONFIGS.keys()),
        help="Promote only this signal type (default: all)"
    )
    args = parser.parse_args()

    types_to_run = (
        {args.signal_type: SIGNAL_CONFIGS[args.signal_type]}
        if args.signal_type
        else SIGNAL_CONFIGS
    )

    total_promoted = total_skipped = 0
    for sig_type, cfg in types_to_run.items():
        min_count = args.min_count if args.min_count > 0 else cfg.default_min_count
        p, s = promote_signal_type(sig_type, cfg, min_count, args.dry_run)
        total_promoted += p
        total_skipped += s

    print(f"\n[promote] total — promoted={total_promoted} skipped={total_skipped}")


if __name__ == "__main__":
    main()
