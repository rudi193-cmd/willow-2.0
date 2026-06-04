"""
core/source_trail.py — Claim verification for source-trail.
b20: SRCTL1  ΔΣ=42

Two-tier verification:
  academic: Jeles trusted sources (29 institutions, via jeles_sources.search)
  press:    HTML scrapers registered in jeles_sources (psychiatric_times, etc.)

Public API:
  extract_claims(text) -> list[str]
  verify_claim(claim, sources, limit) -> dict
  verify_text(text, sources, limit) -> dict

Output schema per claim:
  {claim, matched, title, url, date, source, tier, confidence, institution}
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("source_trail")

_PRESS_SOURCES: frozenset[str] = frozenset({
    "psychiatric_times",
    "stat_news",
    "medscape",
    "ig_nobel",
    "fbi_vault",
    "isfdb",
    "omdb",
})

_EXTRACT_SYSTEM = (
    "Extract the distinct verifiable factual claims from the passage below. "
    "A verifiable claim is a specific, checkable statement: a statistic, a named event, "
    "a study result, a direct quote with attribution, or a stated fact. "
    "Return one claim per line. No bullets, numbers, or preamble. "
    "Skip vague opinions, metaphors, and normative judgements. "
    "Maximum 10 claims. If fewer than 3 verifiable claims exist, return only those."
)


def extract_claims(text: str) -> list[str]:
    """Extract verifiable factual claims from text using the local LLM."""
    try:
        from core.llm_edge import respond
        raw = respond(_EXTRACT_SYSTEM, [], text[:4000])
        lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
        return lines[:10]
    except Exception as exc:
        log.warning("extract_claims failed: %s", exc)
        return []


def verify_claim(
    claim: str,
    sources: Optional[list[str]] = None,
    limit: int = 2,
) -> dict:
    """Verify a single claim against Jeles sources.

    sources=None auto-routes based on claim content.
    Returns the output schema dict (matched=False if nothing found).
    """
    from core.jeles_sources import search as jeles_search, route_sources, _SOURCE_CONFIDENCE

    routed = list(sources) if sources else route_sources(claim)

    raw = jeles_search(claim, routed, limit)
    hits = raw.get("results", {})

    best: Optional[dict] = None
    best_conf: float = 0.0

    for source_id, source_hits in hits.items():
        conf = _SOURCE_CONFIDENCE.get(source_id, 0.70)
        for hit in source_hits:
            if conf > best_conf:
                best_conf = conf
                best = {
                    "claim":       claim,
                    "matched":     True,
                    "title":       (hit.get("title") or "").strip(),
                    "url":         hit.get("url", ""),
                    "date":        hit.get("date", ""),
                    "source":      source_id,
                    "institution": hit.get("institution", source_id),
                    "tier":        "press" if source_id in _PRESS_SOURCES else "academic",
                    "confidence":  conf,
                }

    if best:
        return best

    return {
        "claim":       claim,
        "matched":     False,
        "title":       "",
        "url":         "",
        "date":        "",
        "source":      "",
        "institution": "",
        "tier":        "",
        "confidence":  0.0,
    }


def verify_text(
    text: str,
    sources: Optional[list[str]] = None,
    limit: int = 2,
) -> dict:
    """Extract factual claims from text and verify each against trusted sources.

    Returns:
      {
        "claims": [verify_claim result, ...],
        "total":   int,
        "matched": int,
      }
    """
    claims = extract_claims(text)
    if not claims:
        return {"claims": [], "total": 0, "matched": 0,
                "note": "No verifiable claims found."}

    results = [verify_claim(c, sources, limit) for c in claims]
    matched = sum(1 for r in results if r.get("matched"))
    return {"claims": results, "total": len(results), "matched": matched}
