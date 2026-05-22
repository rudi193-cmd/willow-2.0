#!/usr/bin/env python3
"""
extract_jeles_corpus.py — Track 1: KB atom verification via Jeles trusted sources.
b17: JXTR1  ΔΣ=42

For each KB atom, searches Jeles' trusted source network to find external
corroboration. Annotates the atom's content field with citations and a
jeles_verified flag. Does not ingest new atoms — verifies existing ones.

Usage:
    WILLOW_AGENT_NAME=hanuman python3 agents/hanuman/bin/extract_jeles_corpus.py --dry-run
    WILLOW_AGENT_NAME=hanuman python3 agents/hanuman/bin/extract_jeles_corpus.py
    WILLOW_AGENT_NAME=hanuman python3 agents/hanuman/bin/extract_jeles_corpus.py --category professor
    WILLOW_AGENT_NAME=hanuman python3 agents/hanuman/bin/extract_jeles_corpus.py --project utety --limit 20
    WILLOW_AGENT_NAME=hanuman python3 agents/hanuman/bin/extract_jeles_corpus.py --force
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from core.pg_bridge import PgBridge
from core.jeles_sources import search as jeles_search

logging.basicConfig(level=logging.INFO, format="%(asctime)s [jxtr] %(message)s")
log = logging.getLogger("jxtr")

# Sources most likely to corroborate factual claims — skip museums/libraries
# unless the atom is in a domain that warrants them.
DEFAULT_SOURCES = [
    "openalex", "crossref", "pubmed", "arxiv", "semantic_scholar",
    "core", "doaj", "europepmc", "zenodo", "datacite",
    "wikidata", "loc", "internet_archive", "smithsonian",
]

SNIPPET_LEN = 120


def _build_query(title: str, summary: str) -> str:
    """Extract a clean search query from atom content.

    Prefers the first substantive sentence of the summary over the title,
    since titles often contain provenance markers or internal names that
    produce noise in external searches.
    """
    import re

    # Strip markdown, provenance markers, and internal identifiers
    def clean(text: str) -> str:
        text = re.sub(r"\*+", "", text)           # bold/italic
        text = re.sub(r"`[^`]+`", "", text)        # inline code
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # links → label
        text = re.sub(r"\((?:session|jeles)/[A-F0-9]+\)", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    # Take first sentence of summary that is long enough to be meaningful
    summary_clean = clean(summary or "")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", summary_clean) if len(s.strip()) > 40]
    if sentences:
        return sentences[0][:140]

    # Fall back to cleaned title
    return clean(title)[:140]


def _summarise_hits(results: dict) -> list[dict]:
    """Flatten source results into a compact citation list."""
    citations = []
    for source_id, hits in results.items():
        for hit in hits:
            citations.append({
                "source": source_id,
                "institution": hit.get("institution", ""),
                "title": hit.get("title", "")[:160],
                "url": hit.get("url", ""),
                "snippet": hit.get("snippet", "")[:SNIPPET_LEN],
                "date": hit.get("date", ""),
            })
    return citations


def _score_relevance(claim: str, citations: list[dict]) -> tuple[float, list[dict]]:
    """Use infer_7b(classify) to score whether citations corroborate the claim.

    Returns (relevance_score, filtered_citations) where relevance_score is
    0.0-1.0 and filtered_citations contains only those judged relevant.
    Falls back to raw citation count heuristic if orin is unavailable.
    """
    if not citations:
        return 0.0, []

    # Build a compact digest of the top citations for orin to evaluate
    digest = "\n".join(
        f"- [{c['source']}] {c['title']} — {c['snippet'][:80]}"
        for c in citations[:5]
    )
    content = f"Claim: {claim}\n\nCitations found:\n{digest}"

    try:
        from agents.orin.tasks import classify
        result = classify(
            content,
            ["corroborates", "unrelated", "contradicts"],
            context=(
                "Does the citation list corroborate, contradict, or is it unrelated "
                "to the claim? Score corroborates=1.0, unrelated=0.1, contradicts=0.0."
            ),
        )
        r = result.get("result", {})
        category = r.get("category", "unrelated")
        conf     = float(r.get("confidence", 0.5))

        if category == "corroborates":
            return conf, citations
        elif category == "contradicts":
            return 0.0, []
        else:
            return 0.1, []

    except Exception:
        # Fallback: any hit is weak evidence
        return min(0.5, len(citations) * 0.1), citations


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify KB atoms against Jeles trusted sources")
    parser.add_argument("--dry-run",  action="store_true", help="Search but do not write back to KB")
    parser.add_argument("--no-llm",   action="store_true", help="Skip infer_7b relevance scoring")
    parser.add_argument("--category", default="", help="Filter by category")
    parser.add_argument("--domain",   default="", help="Filter by domain")
    parser.add_argument("--project",  default="", help="Filter by project")
    parser.add_argument("--limit",    type=int, default=0, help="Max atoms to process (0=all)")
    parser.add_argument("--force",    action="store_true", help="Re-verify atoms already checked")
    parser.add_argument("--sources",  nargs="+", default=DEFAULT_SOURCES,
                        help="Jeles source IDs to query")
    args = parser.parse_args()

    pg = PgBridge()

    conditions = ["invalid_at IS NULL"]
    params: list = []

    if args.category:
        conditions.append("category = %s")
        params.append(args.category)
    if args.domain:
        conditions.append("domain = %s")
        params.append(args.domain)
    if args.project:
        conditions.append("project = %s")
        params.append(args.project)
    if not args.force:
        conditions.append("(content->>'jeles_checked_at') IS NULL")

    where = " AND ".join(conditions)
    query_sql = f"SELECT id, title, summary FROM knowledge WHERE {where} ORDER BY valid_at DESC"
    if args.limit:
        query_sql += f" LIMIT {args.limit}"

    with pg.conn.cursor() as cur:
        cur.execute(query_sql, params)
        atoms = cur.fetchall()

    log.info("Atoms to verify: %d  sources: %s", len(atoms), ", ".join(args.sources))

    verified = 0
    unverified = 0

    for atom_id, title, summary in atoms:
        query = _build_query(title, summary or "")
        log.info("Searching: [%s] %s", atom_id, query[:80])

        result = jeles_search(query, sources=args.sources, limit_per_source=3)
        citations = _summarise_hits(result.get("results", {}))
        total_hits = result.get("total", 0)
        checked_at = datetime.now(timezone.utc).isoformat()

        if args.no_llm:
            relevance_score = float(min(1.0, total_hits * 0.1)) if total_hits else 0.0
            filtered_citations = citations
        else:
            relevance_score, filtered_citations = _score_relevance(query, citations)

        is_verified = relevance_score >= 0.5

        if args.dry_run:
            status = f"✓ {total_hits} hits  score={relevance_score:.2f}" if total_hits else "✗ no hits"
            log.info("  [DRY] %s  citations=%d  filtered=%d", status, len(citations), len(filtered_citations))
            if filtered_citations:
                for c in filtered_citations[:2]:
                    log.info("        %s — %s", c["source"], c["title"][:80])
            verified += (1 if is_verified else 0)
            unverified += (0 if is_verified else 1)
            continue

        annotation = {
            "jeles_verified": is_verified,
            "jeles_checked_at": checked_at,
            "jeles_citation_count": total_hits,
            "jeles_relevance_score": round(relevance_score, 4),
            "jeles_citations": filtered_citations[:10],
        }

        with pg.conn.cursor() as cur:
            cur.execute(
                "UPDATE knowledge SET content = content || %s::jsonb WHERE id = %s",
                (json.dumps(annotation), atom_id),
            )
        pg.conn.commit()

        if is_verified:
            log.info("  ✓ verified — %d hits  score=%.2f  filtered=%d",
                     total_hits, relevance_score, len(filtered_citations))
            verified += 1
        else:
            log.info("  ✗ no corroboration — hits=%d  score=%.2f", total_hits, relevance_score)
            unverified += 1

    log.info("Done. verified=%d  unverified=%d", verified, unverified)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
