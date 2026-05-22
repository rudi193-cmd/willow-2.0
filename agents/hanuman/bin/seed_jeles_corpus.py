#!/usr/bin/env python3
"""
seed_jeles_corpus.py — Track 1: topic → Jeles search → jeles_atoms seeding.
b17: JXSD1  ΔΣ=42

Given a topic, searches Jeles' trusted source network, classifies results for
relevance, and seeds matching hits into intake (tier=fetched). norn-pass
promotes them to jeles_atoms.

Usage:
    python3 agents/hanuman/bin/seed_jeles_corpus.py --topic "Byzantine iconography"
    python3 agents/hanuman/bin/seed_jeles_corpus.py --topic "entropy in complex systems" --sources openalex arxiv crossref
    python3 agents/hanuman/bin/seed_jeles_corpus.py --topic "Edo period painting" --dry-run
    python3 agents/hanuman/bin/seed_jeles_corpus.py --topic "machine learning fairness" --min-score 0.6 --limit 10
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from core.jeles_sources import search as jeles_search, SOURCES, _SOURCE_CONFIDENCE
from core.intake import write as intake_write

logging.basicConfig(level=logging.INFO, format="%(asctime)s [jxsd] %(message)s")
log = logging.getLogger("jxsd")

# Default sources: all that don't require an API key
DEFAULT_SOURCES = [
    sid for sid, cfg in SOURCES.items() if not cfg["key_required"]
]

SNIPPET_LEN = 200


def _score_relevance(topic: str, hit: dict) -> float:
    """Score whether a single search hit is relevant to the topic.

    Uses orin classify. Falls back to 0.5 (neutral) if orin is unavailable.
    """
    title = hit.get("title", "")
    snippet = hit.get("snippet", "")[:SNIPPET_LEN]
    content = f"Topic: {topic}\n\nResult title: {title}\nSnippet: {snippet}"

    try:
        from agents.orin.tasks import classify
        result = classify(
            content,
            ["relevant", "unrelated"],
            context=(
                "Is this search result relevant to the given topic? "
                "Score: relevant=1.0, unrelated=0.0."
            ),
        )
        r = result.get("result", {})
        category = r.get("category", "unrelated")
        conf = float(r.get("confidence", 0.5))
        return conf if category == "relevant" else (1.0 - conf) * 0.1
    except Exception:
        # Fallback: assume weakly relevant if there's a title
        return 0.4 if title else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed jeles_atoms from a topic search across trusted sources"
    )
    parser.add_argument("--topic",            required=True,  help="Search topic or query")
    parser.add_argument("--sources",          nargs="+",      default=DEFAULT_SOURCES,
                        help="Jeles source IDs to query (default: all no-key sources)")
    parser.add_argument("--limit",            type=int,       default=5,
                        help="Results per source (default: 5)")
    parser.add_argument("--min-score",        type=float,     default=0.5,
                        help="Minimum relevance score to seed (default: 0.5)")
    parser.add_argument("--dry-run",          action="store_true",
                        help="Search and classify but do not write to intake")
    parser.add_argument("--no-llm",           action="store_true",
                        help="Skip orin classify — accept all hits above 0 results")
    parser.add_argument("--agent",            default="hanuman",
                        help="Agent name for intake write (default: hanuman)")
    args = parser.parse_args()

    log.info("Topic: %r  sources: %d  limit/source: %d", args.topic, len(args.sources), args.limit)

    result = jeles_search(args.topic, sources=args.sources, limit_per_source=args.limit)
    total_hits = result.get("total", 0)
    results_by_source = result.get("results", {})

    log.info("Search complete — %d hits across %d sources", total_hits, len(results_by_source))

    seeded = 0
    skipped = 0

    for source_id, hits in results_by_source.items():
        confidence_base = _SOURCE_CONFIDENCE.get(source_id, 0.80)

        for hit in hits:
            title = hit.get("title", "").strip()
            if not title:
                skipped += 1
                continue

            if args.no_llm:
                score = confidence_base
            else:
                score = _score_relevance(args.topic, hit)

            url = hit.get("url", "")
            snippet = hit.get("snippet", "")[:SNIPPET_LEN]
            date = hit.get("date", "")
            institution = hit.get("institution", "")

            content_lines = [f"Source: {institution or source_id}"]
            if date:
                content_lines.append(f"Date: {date}")
            if url:
                content_lines.append(f"URL: {url}")
            if snippet:
                content_lines.append(f"\n{snippet}")
            content = "\n".join(content_lines)

            status = f"score={score:.2f}"
            if score >= args.min_score:
                status += " ✓"
            else:
                status += " ✗ (below threshold)"

            log.info("  [%s] %s — %s", source_id, title[:80], status)

            if score < args.min_score:
                skipped += 1
                continue

            if args.dry_run:
                seeded += 1
                continue

            intake_write(
                content=content,
                source=url or source_id,
                agent=args.agent,
                tier="fetched",
                confidence=round(min(confidence_base, score), 4),
                title=title,
                keywords=[w.lower() for w in args.topic.split() if len(w) > 3][:8],
                tags=[source_id, "jeles", "track1", f"topic:{args.topic[:40]}"],
                extra={
                    "domain": ",".join(SOURCES.get(source_id, {}).get("domain", [source_id])[:2]),
                    "category": "jeles_seed",
                },
            )
            seeded += 1

    action = "would seed" if args.dry_run else "seeded"
    log.info("Done. %s=%d  skipped=%d  total_hits=%d", action, seeded, skipped, total_hits)
    if args.dry_run:
        log.info("[DRY RUN] no intake writes performed")
    elif seeded:
        log.info("Run promote_intake.py to promote fetched records to jeles_atoms")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
