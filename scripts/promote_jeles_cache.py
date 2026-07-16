#!/usr/bin/env python3
"""
promote_jeles_cache.py — norn-pass: promote Jeles web search cache to jeles_atoms.
b17: JLSP1  ΔΣ=42

Reads ~/.willow/jeles_cache/*.jsonl. Groups results by URL (dedup).
Promotes records that meet either threshold:
  - hit_count >= --min-hits (same URL retrieved across multiple queries)
  - confidence >= --min-confidence (primary institution source, single hit is enough)

On first run, registers a sentinel jeles_session for web cache results and
stores its ID in ~/.willow/jeles_cache/.meta.json.

Usage:
    WILLOW_AGENT_NAME=hanuman python3 scripts/promote_jeles_cache.py --dry-run
    WILLOW_AGENT_NAME=hanuman python3 scripts/promote_jeles_cache.py
    WILLOW_AGENT_NAME=hanuman python3 scripts/promote_jeles_cache.py --min-hits 1 --min-confidence 0.90
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from core.agent_identity import require_agent_name
from core.pg_bridge import PgBridge
from willow.fylgja.willow_home import willow_home

AGENT      = require_agent_name()
CACHE_DIR  = willow_home(_REPO_ROOT) / "jeles_cache"
META_FILE  = CACHE_DIR / ".meta.json"

_HIGH_CONFIDENCE_THRESHOLD = 0.90   # promote single-hit if confidence >= this
_DEFAULT_MIN_HITS = 2               # promote multi-hit if seen >= this many times


def _load_meta() -> dict:
    try:
        return json.loads(META_FILE.read_text())
    except Exception:
        return {}


def _save_meta(meta: dict) -> None:
    META_FILE.write_text(json.dumps(meta, indent=2))


def _ensure_sentinel_session(pg: PgBridge, meta: dict) -> str:
    """Return sentinel jeles_session ID, registering it if needed."""
    sid = meta.get("web_cache_session_id")
    if sid:
        return sid
    result = pg.jeles_register_jsonl(
        agent=AGENT,
        jsonl_path=str(CACHE_DIR),
        session_id="jeles_web_cache",
        cwd=str(_REPO_ROOT),
        turn_count=0,
        file_size=0,
    )
    sid = result.get("id")
    if not sid:
        raise RuntimeError(f"Failed to register sentinel session: {result}")
    meta["web_cache_session_id"] = sid
    _save_meta(meta)
    return sid


def _load_cache() -> list[dict]:
    records = []
    for jsonl_file in sorted(CACHE_DIR.glob("*.jsonl")):
        try:
            for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            print(f"[promote] could not read {jsonl_file.name}: {e}", file=sys.stderr)
    return records


def _mark_promoted_in_cache(url: str) -> None:
    """Rewrite cache files marking all records with this URL as promoted."""
    promoted_at = datetime.now(timezone.utc).isoformat()
    for jsonl_file in sorted(CACHE_DIR.glob("*.jsonl")):
        try:
            lines = jsonl_file.read_text(encoding="utf-8").splitlines()
            updated = []
            changed = False
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("url") == url and not rec.get("promoted"):
                        rec["promoted"] = True
                        rec["promoted_at"] = promoted_at
                        changed = True
                    updated.append(json.dumps(rec, ensure_ascii=False))
                except json.JSONDecodeError:
                    updated.append(line)
            if changed:
                jsonl_file.write_text("\n".join(updated) + "\n", encoding="utf-8")
        except Exception as e:
            print(f"[promote] mark promoted failed for {jsonl_file.name}: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote Jeles web cache to jeles_atoms")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-hits", type=int, default=_DEFAULT_MIN_HITS,
                        help=f"Promote if URL seen >= N times (default: {_DEFAULT_MIN_HITS})")
    parser.add_argument("--min-confidence", type=float, default=_HIGH_CONFIDENCE_THRESHOLD,
                        help=f"Also promote single-hit results with confidence >= N (default: {_HIGH_CONFIDENCE_THRESHOLD})")
    args = parser.parse_args()

    if not CACHE_DIR.exists():
        print("[promote] cache dir not found — run mem_jeles_web_search first")
        return

    records = _load_cache()
    if not records:
        print("[promote] no cache records found")
        return

    pending = [r for r in records if not r.get("promoted")]
    print(f"[promote] {len(records)} total, {len(pending)} pending")

    # Group by URL — dedup, accumulate hits
    groups: dict[str, list[dict]] = defaultdict(list)
    for rec in pending:
        url = rec.get("url", "")
        if url:
            groups[url].append(rec)

    pg = PgBridge() if not args.dry_run else None
    meta = _load_meta() if not args.dry_run else {}
    sentinel_id = _ensure_sentinel_session(pg, meta) if not args.dry_run else "dry-run"

    promoted = 0
    skipped = 0

    for url, hits in sorted(groups.items(), key=lambda x: -len(x[1])):
        canonical = hits[0]
        hit_count = len(hits)
        confidence = max(r.get("confidence", 0.80) for r in hits)
        meets_threshold = (
            hit_count >= args.min_hits
            or confidence >= args.min_confidence
        )

        if not meets_threshold:
            skipped += 1
            continue

        title = canonical.get("title", "")[:200] or url
        content = "\n".join(filter(None, [
            canonical.get("snippet", ""),
            f"Source: {canonical.get('institution', '')}",
            f"Date: {canonical.get('date', '')}",
            f"URL: {url}",
        ]))
        domain = (canonical.get("tags") or [canonical.get("source", "general")])[0]
        queries = list({r.get("query", "") for r in hits if r.get("query")})

        if args.dry_run:
            print(f"  [dry-run] would promote ({hit_count}x, conf={confidence:.2f}): {title[:70]}")
            print(f"    source={canonical.get('source')} queries={queries[:2]}")
            promoted += 1
            continue

        try:
            result = pg.jeles_extract_atom(
                agent=AGENT,
                jsonl_id=sentinel_id,
                content=content,
                domain=domain,
                depth=1,
                confidence=confidence,
                title=title,
            )
            if result.get("error"):
                print(f"  [error] {result['error']} — {title[:60]}", file=sys.stderr)
            else:
                atom_id = result.get("id", "?")
                print(f"  [promoted] {atom_id} ({hit_count}x, conf={confidence:.2f}): {title[:60]}")
                _mark_promoted_in_cache(url)
                promoted += 1
        except Exception as e:
            print(f"  [error] {e} — {title[:60]}", file=sys.stderr)

    print(f"[promote] done — promoted={promoted} skipped={skipped} "
          f"(min_hits={args.min_hits}, min_conf={args.min_confidence})")


if __name__ == "__main__":
    main()
