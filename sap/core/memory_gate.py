"""Pre-ingest duplicate / overlap heuristics for willow_memory_check (MCP).
b17: 449E3  ΔΣ=42

Checks a candidate atom before write. sap_mcp.py blocks REDUNDANT and
CONTRADICTION by default; pass force=True to override. STALE and DARK
remain advisory — sap_mcp.py does not block on them.
"""
from __future__ import annotations

import re
import sys
from typing import Any, Optional

__all__ = ["check_candidate"]


def _title_tokens(s: str) -> set[str]:
    """Tokenise a short title — drops tokens < 2 chars."""
    s = s.casefold().strip()
    if not s:
        return set()
    return {p for p in re.split(r"[^\w]+", s) if len(p) > 1}


def _summary_tokens(s: str) -> set[str]:
    """Tokenise a longer summary — drops tokens < 3 chars for less noise."""
    s = s.casefold().strip()
    if not s:
        return set()
    return {p for p in re.split(r"[^\w]+", s) if len(p) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _kb_scan(pg: Any, *, title: str, domain: Optional[str]) -> list[dict[str, Any]]:
    q = (title or "").strip() or (domain or "").strip()
    if not q:
        return []
    project = (domain or "").strip() or None
    try:
        if project:
            return pg.knowledge_search(q, project=project, limit=20)
        return pg.knowledge_search(q, limit=20)
    except Exception:
        try:
            return pg.knowledge_search(q, limit=20)
        except Exception:
            return []


def _soil_scan(store: Any, collection: str, title: str) -> list[dict[str, Any]]:
    if not collection or store is None:
        return []
    q = (title or "").strip()
    if not q:
        return []
    try:
        return store.search(collection, q)
    except Exception:
        return []


def check_candidate(
    *,
    title: str,
    summary: str,
    domain: Optional[str],
    store: Any,
    pg: Any,
    collection: Optional[str] = None,
) -> dict[str, Any]:
    """Score a candidate KB/SOIL write before ingest.

    Returns flags (subset of REDUNDANT, STALE, DARK, CONTRADICTION),
    human recommendation, and compact evidence for debugging.
    """
    from core.agent_identity import require_agent_name
    _agent = require_agent_name()
    _collection = collection or (f"{domain}/atoms" if domain else f"{_agent}/atoms")
    flags: list[str] = []
    evidence: dict[str, Any] = {}

    title_s  = (title or "").strip()
    summary_s = (summary or "").strip()
    t_norm   = title_s.casefold()

    # ── Postgres knowledge ────────────────────────────────────────────────────
    kb_hits: list[dict[str, Any]] = []
    if pg is not None:
        kb_hits = _kb_scan(pg, title=title_s, domain=domain)
        evidence["kb_ids"] = [r.get("id") for r in kb_hits[:8]]

        for row in kb_hits:
            rt = (row.get("title") or "").strip().casefold()
            if t_norm and rt == t_norm:
                if "REDUNDANT" not in flags:
                    flags.append("REDUNDANT")
                evidence["kb_exact_title_id"] = row.get("id")
                break
            if t_norm and rt:
                j = _jaccard(_title_tokens(title_s), _title_tokens(row.get("title") or ""))
                if j >= 0.85 and len(_title_tokens(title_s)) >= 2:
                    if "REDUNDANT" not in flags:
                        flags.append("REDUNDANT")
                    evidence["kb_near_title_id"] = row.get("id")
                    break

        # CONTRADICTION: candidate title matches an existing row but their
        # summaries diverge significantly — candidate vs. existing, not
        # existing rows vs. each other.
        same_title_rows = [
            r for r in kb_hits
            if (r.get("title") or "").strip().casefold() == t_norm
        ]
        if same_title_rows and summary_s:
            c_tokens = _summary_tokens(summary_s)
            for row in same_title_rows:
                exist_sum = (row.get("summary") or "").strip()
                if len(exist_sum) < 40 or not c_tokens:
                    continue
                j = _jaccard(c_tokens, _summary_tokens(exist_sum))
                if j < 0.3:
                    if "CONTRADICTION" not in flags:
                        flags.append("CONTRADICTION")
                        evidence["contradiction_ids"] = [
                            r.get("id") for r in same_title_rows[:5]
                        ]
                    break

        # STALE: candidate summary largely contained in an existing atom.
        # Uses _summary_tokens for less noisy overlap on longer text.
        if summary_s:
            c_tokens = _summary_tokens(summary_s)
            for row in kb_hits:
                exist = (row.get("summary") or "").strip()
                if len(exist) < 40:
                    continue
                et = _summary_tokens(exist)
                if c_tokens and et:
                    j = _jaccard(c_tokens, et)
                    if j >= 0.75 and len(summary_s) < len(exist) * 0.6:
                        if "STALE" not in flags:
                            flags.append("STALE")
                            evidence["stale_vs_id"] = row.get("id")
                        break

    # ── SOIL collection ───────────────────────────────────────────────────────
    soil_hits = _soil_scan(store, _collection, title_s)
    evidence["soil_ids"] = [r.get("id") for r in soil_hits[:8] if isinstance(r, dict)]

    for rec in soil_hits:
        if not isinstance(rec, dict):
            continue
        rt = (rec.get("title") or rec.get("subject") or "").strip().casefold()
        if t_norm and rt == t_norm and "REDUNDANT" not in flags:
            flags.append("REDUNDANT")
            evidence["soil_exact_title_id"] = rec.get("id")
            break

    # ── DARK: probable protected / identity-minimal records ──────────────────
    dark_markers = ("identity protection", "protected record", "do not name", "initial only")
    blob = f"{title_s} {summary_s}".casefold()
    if any(m in blob for m in dark_markers):
        if "DARK" not in flags:
            flags.append("DARK")

    # ── Recommendation ────────────────────────────────────────────────────────
    if "REDUNDANT" in flags:
        rec = "Likely duplicate of an existing atom or SOIL record; skip ingest or fetch existing id and update/archive explicitly."
    elif "CONTRADICTION" in flags:
        rec = "Candidate title matches an existing row but summaries diverge; resolve or force=True to override."
    elif "STALE" in flags:
        rec = "Existing atom appears to supersede this summary; consider updating the prior atom instead of inserting."
    elif "DARK" in flags:
        rec = "Sensitive or identity-protected phrasing detected; confirm Sean-authorized wording before ingest."
    elif kb_hits or soil_hits:
        rec = "No hard duplicate signal; still run willow_knowledge_search with distinctive keywords before ingest."
    else:
        rec = "No overlapping hits on quick scan; ingest is reasonable if domain/title are intentional."

    return {
        "flags": flags,
        "recommendation": rec,
        "evidence": evidence,
    }
