#!/usr/bin/env python3
"""
core/actr.py — ACT-R base-level activation for atom retrieval scoring.
b17: ACTR1  ΔΣ=42

Implements the ACT-R base-level learning equation (Anderson 1983):
    A = B - d * ln(T)

where:
    B = base level (derived from atom importance, normalized 0–1)
    d = decay parameter (default 0.5 per ACT-R spec)
    T = recency in seconds since last interaction (creation proxy)

Atoms with higher activation are more worth retrieving. When presenting
a list to an LLM, sort ascending (lowest first) so the highest-activation
atom lands last — recency bias in the context window makes the final item
the most salient.

Usage:
    from core.actr import activation, score_atoms

    a = activation(base_level=0.8, recency_seconds=3600)
    ranked = score_atoms(atoms, now=datetime.now(timezone.utc))
    # ranked[-1] is the most activation-relevant atom
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional


def activation(
    base_level: float,
    recency_seconds: float,
    decay: float = 0.5,
) -> float:
    """Return ACT-R base-level activation for a single atom.

    base_level: 0.0–1.0 (normalize importance/10 before passing)
    recency_seconds: seconds since last interaction (creation used as proxy)
    decay: ACT-R decay parameter d (default 0.5)
    """
    if recency_seconds <= 0:
        recency_seconds = 1.0
    return base_level - decay * math.log(recency_seconds)


def _parse_dt(ts: str | None) -> Optional[datetime]:
    """Parse ISO timestamp string, return aware datetime or None."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def score_atoms(
    atoms: list[dict],
    now: Optional[datetime] = None,
    decay: float = 0.5,
    importance_field: str = "importance",
    timestamp_field: str = "valid_at",
    max_importance: float = 10.0,
) -> list[dict]:
    """Score atoms by ACT-R activation and sort ascending (most relevant last).

    atoms: list of atom dicts (SOIL records or KB atoms)
    now: reference time (UTC). Defaults to utcnow.
    decay: ACT-R decay parameter (default 0.5)
    importance_field: atom field carrying 1–10 importance score
    timestamp_field: atom field carrying ISO creation/valid timestamp
    max_importance: divisor to normalize importance → 0–1

    Returns the same list sorted ascending by activation score.
    Each atom gets an "_activation" key added.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    scored = []
    for atom in atoms:
        imp = float(atom.get(importance_field) or 5)
        base = max(0.0, min(1.0, imp / max_importance))

        ts_str = atom.get(timestamp_field) or atom.get("created_at") or atom.get("valid_at")
        dt = _parse_dt(ts_str)
        if dt:
            recency = max(1.0, (now - dt).total_seconds())
        else:
            recency = 86400.0  # default 1 day if no timestamp

        score = activation(base, recency, decay)
        scored.append({**atom, "_activation": score})

    scored.sort(key=lambda a: a["_activation"])
    return scored
