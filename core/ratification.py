"""
ratification.py — Two-class ratification classifier.
b17: RTFY1  ΔΣ=42

Pure function — no I/O. Classifies a pending intake/drift record as either
evidence_based (safe to auto-ratify) or judgment_based (requires human triage).

Judgment always wins: if any judgment signal fires, the record is judgment_based
regardless of evidence signals.
"""
from __future__ import annotations

_JUDGMENT_CATEGORIES = frozenset({"correction", "architecture", "decision", "canonical"})
_JUDGMENT_SOURCES    = frozenset({"correction", "feedback", "preference", "sean"})
_EVIDENCE_CATEGORIES = frozenset({"pattern", "reference", "knowledge"})
_EVIDENCE_SOURCES    = frozenset({"code", "drift", "test", "ci"})

_EVIDENCE_TIER_MIN_CONFIDENCE = 0.90
_EVIDENCE_TIERS = frozenset({"fetched", "verified"})


def classify_ratification_class(record: dict) -> str:
    """Return 'evidence_based' or 'judgment_based' for a pending record.

    Rules applied in order:
    1. Tier == canonical → always judgment_based
    2. Category in judgment set → judgment_based
    3. Source contains any judgment keyword → judgment_based
    4. Source contains any evidence keyword → evidence_based
    5. Tier in (fetched, verified) + confidence >= 0.90 → evidence_based
    6. Category in evidence set (no judgment signals above) → evidence_based
    7. Default → judgment_based
    """
    tier       = record.get("tier", "observed")
    category   = record.get("category", "")
    source     = record.get("source", "")
    confidence = float(record.get("confidence", 0.0))

    # 1. Canonical always judgment
    if tier == "canonical":
        return "judgment_based"

    # 2. Judgment category
    if category in _JUDGMENT_CATEGORIES:
        return "judgment_based"

    # 3. Judgment source keywords
    source_lower = source.lower()
    if any(kw in source_lower for kw in _JUDGMENT_SOURCES):
        return "judgment_based"

    # 4. Evidence source keywords (code, drift, test, ci) → auto-ratify
    if any(kw in source_lower for kw in _EVIDENCE_SOURCES):
        return "evidence_based"

    # 5. Trusted tier + high confidence
    if tier in _EVIDENCE_TIERS and confidence >= _EVIDENCE_TIER_MIN_CONFIDENCE:
        return "evidence_based"

    # 6. Evidence category (no judgment signals fired)
    if category in _EVIDENCE_CATEGORIES:
        return "evidence_based"

    return "judgment_based"
