#!/usr/bin/env python3
"""
promote_corrections.py — norn-pass: promote recurring corrections to knowledge table.

Reads corpus/corrections from WillowStore. Groups by normalized content.
Corrections that appear in 2+ sessions are promoted to knowledge via kb_ingest
with tier='observed', confidence=0.8. Single-occurrence corrections are skipped
(too noisy). Already-promoted records are marked and skipped on re-run.

Usage:
    python3 scripts/promote_corrections.py [--dry-run] [--min-count N]
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from core.agent_identity import require_agent_name
from willow.fylgja._mcp import call

AGENT = require_agent_name()


def _normalize(text: str) -> str:
    """Lowercase, strip, collapse whitespace for grouping."""
    import re
    return re.sub(r"\s+", " ", text.lower().strip())[:200]


def _load_corrections() -> list[dict]:
    try:
        from core.willow_store import WillowStore
        store = WillowStore()
        return store.all("corpus/corrections") or []
    except Exception as e:
        print(f"[promote] failed to load corrections: {e}", file=sys.stderr)
        return []


def _mark_promoted(record_ids: list[str]) -> None:
    try:
        from core.willow_store import WillowStore
        store = WillowStore()
        for rid in record_ids:
            rec = store.get("corpus/corrections", rid)
            if rec:
                rec["promoted"] = True
                rec["promoted_at"] = datetime.now(timezone.utc).isoformat()
                store.update("corpus/corrections", rid, rec)
    except Exception as e:
        print(f"[promote] mark promoted failed: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote recurring corrections to KB")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-count", type=int, default=2,
                        help="Minimum occurrences before promoting (default: 2)")
    args = parser.parse_args()

    corrections = _load_corrections()
    if not corrections:
        print("[promote] no corrections found")
        return

    # Skip already promoted
    pending = [c for c in corrections if not c.get("promoted")]
    print(f"[promote] {len(corrections)} total, {len(pending)} pending")

    # Group by normalized content
    groups: dict[str, list[dict]] = defaultdict(list)
    for c in pending:
        key = _normalize(c.get("content", ""))
        if key:
            groups[key].append(c)

    promoted = 0
    skipped = 0
    for norm_content, records in sorted(groups.items(), key=lambda x: -len(x[1])):
        if len(records) < args.min_count:
            skipped += 1
            continue

        sessions = list({r.get("session_id", "")[:8] for r in records if r.get("session_id")})
        canonical = records[0].get("content", norm_content)[:300]
        source = records[0].get("source", "hook")
        title = f"correction: {canonical[:60]}"
        confidence = min(0.6 + len(records) * 0.1, 0.95)

        tags = ["correction", AGENT, source, f"count:{len(records)}"]
        keywords = [w for w in norm_content.split() if len(w) > 4][:8]

        if args.dry_run:
            print(f"  [dry-run] would promote ({len(records)}x, sessions {sessions[:3]}): {canonical[:80]}")
            promoted += 1
            continue

        try:
            result = call("kb_ingest", {
                "app_id":      AGENT,
                "title":       title,
                "summary":     canonical,
                "source_type": "norn_pass",
                "source_id":   f"corrections:{len(records)}",
                "category":    "correction",
                "keywords":    keywords,
                "tags":        tags,
                "tier":        "observed",
                "confidence":  confidence,
            }, timeout=15)
            if result.get("blocked"):
                print(f"  [blocked] {title[:60]} — {result.get('flags')}")
            else:
                atom_id = result.get("id", "?")
                print(f"  [promoted] {atom_id} ({len(records)}x): {canonical[:60]}")
                _mark_promoted([r["id"] for r in records if r.get("id")])
                promoted += 1
        except Exception as e:
            print(f"  [error] {e} — {canonical[:60]}", file=sys.stderr)

    print(f"[promote] done — promoted={promoted} skipped={skipped} (min_count={args.min_count})")


if __name__ == "__main__":
    main()
