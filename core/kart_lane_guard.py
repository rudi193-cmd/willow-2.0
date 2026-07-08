"""Kart lane guard — suggest batch for long work; warn on fast-lane mismatches."""
from __future__ import annotations

import re

from core.kart_lanes import KART_LANE_BATCH, KART_LANE_FAST, normalize_lane

# Shell/script fragments that belong on the batch worker, not the fast lane.
_BATCH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"promote_intake", re.I),
    re.compile(r"auto_dream", re.I),
    re.compile(r"wce_witness", re.I),
    re.compile(r"willow_embed_backfill", re.I),
    re.compile(r"index_repository", re.I),
    re.compile(r"kb_intelligence", re.I),
    re.compile(r"\bollama\b", re.I),
    re.compile(r"\bembed(?:ding)?\b", re.I),
    re.compile(r"\bingest\b", re.I),
    re.compile(r"# allow_localhost\b", re.I),
)


def suggest_lane(task_text: str) -> str:
    """Return ``batch`` when task text matches known long-running work."""
    text = task_text or ""
    for pat in _BATCH_PATTERNS:
        if pat.search(text):
            return KART_LANE_BATCH
    return KART_LANE_FAST


def lane_mismatch_warning(task_text: str, lane: str | None) -> dict | None:
    """Warn when heavy work is queued on the fast lane."""
    norm = normalize_lane(lane)
    suggested = suggest_lane(task_text)
    if suggested == KART_LANE_BATCH and norm == KART_LANE_FAST:
        return {
            "warning": "task looks like long batch work but lane=fast",
            "suggested_lane": KART_LANE_BATCH,
            "lane": norm,
        }
    return None
