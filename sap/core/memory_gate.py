"""Pre-ingest duplicate / overlap heuristics for willow_memory_check (MCP).
b17: 449E3  ΔΣ=42

Conservative v1: exact title match against active Postgres knowledge rows
and substring token overlap against a SOIL collection. Does not block
ingest — callers interpret flags + recommendation.
"""
from __future__ import annotations

import re
from typing import Any, Optional

__all__ = ["check_candidate"]


def _title_tokens(s: str) -> set[str]:
    s = s.casefold().strip()
    if not s:
        return set()
    parts = re.split(r"[^\w]+", s)
    return {p for p in parts if len(p) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _kb_scan(
    pg: Any,
    *,
    title: str,
    domain: Optional[str],
) -> list[dict[str, Any]]:
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
    collection: str = "hanuman/atoms",
) -> dict[str, Any]:
    """
    Score a candidate KB / SOIL write before ingest.

    Returns ``flags`` (subset of REDUNDANT, STALE, DARK, CONTRADICTION),
    human ``recommendation``, and compact ``evidence`` for debugging.
    """
    flags: list[str] = []
    evidence: dict[str, Any] = {}

    title_s = (title or "").strip()
    summary_s = (summary or "").strip()
    t_norm = title_s.casefold()

    # --- Postgres knowledge -------------------------------------------------
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

        # Light contradiction: same normalized title, very different summaries
        same_title_rows = [r for r in kb_hits if (r.get("title") or "").strip().casefold() == t_norm]
        if len(same_title_rows) > 1:
            sums = {(r.get("summary") or "").strip() for r in same_title_rows}
            if len(sums) > 1 and "CONTRADICTION" not in flags:
                flags.append("CONTRADICTION")
                evidence["contradiction_ids"] = [r.get("id") for r in same_title_rows[:5]]

        # STALE: candidate summary largely contained in an existing atom
        if summary_s:
            s_tokens = _title_tokens(summary_s)
            for row in kb_hits:
                exist = (row.get("summary") or "").strip()
                if len(exist) < 40:
                    continue
                et = _title_tokens(exist)
                if s_tokens and et:
                    j = _jaccard(s_tokens, et)
                    if j >= 0.75 and len(summary_s) < len(exist) * 0.6:
                        if "STALE" not in flags:
                            flags.append("STALE")
                            evidence["stale_vs_id"] = row.get("id")
                        break

    # --- SOIL collection ----------------------------------------------------
    soil_hits = _soil_scan(store, collection, title_s)
    evidence["soil_ids"] = [r.get("id") for r in soil_hits[:8] if isinstance(r, dict)]

    for rec in soil_hits:
        if not isinstance(rec, dict):
            continue
        rt = (rec.get("title") or rec.get("subject") or "").strip().casefold()
        if t_norm and rt == t_norm and "REDUNDANT" not in flags:
            flags.append("REDUNDANT")
            evidence["soil_exact_title_id"] = rec.get("id")
            break

    # --- DARK: probable protected / identity-minimal records ----------------
    dark_markers = ("identity protection", "protected record", "do not name", "initial only")
    blob = f"{title_s} {summary_s}".casefold()
    if any(m in blob for m in dark_markers):
        if "DARK" not in flags:
            flags.append("DARK")

    # --- Recommendation -----------------------------------------------------
    if "REDUNDANT" in flags:
        rec = "Likely duplicate of an existing atom or SOIL record; skip ingest or fetch existing id and update/archive explicitly."
    elif "CONTRADICTION" in flags:
        rec = "Multiple live rows share this title with different bodies; resolve in KB before adding another."
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
