"""Relevance floor for Jeles discovery serendipity bridges (#653).

Discovery passes bridge hits into the civics corpus when token overlap is
LOW — odd bridges are the point — but 1–2 generic tokens ("United States")
produce false bridges (MusicBrainz Carla Bley recording → federalism atom).

A bridge passes the floor only when:

1. at least one overlapping token is informative (not corpus-generic), and
2. embedding cosine similarity between hit text and corpus atom text clears
   the floor (JELES_BRIDGE_MIN_COSINE, default 0.45).

Fail-closed: if the embedder is unavailable the bridge is rejected — a
missed odd edge is cheaper than another 725-edge noise pass.
"""
from __future__ import annotations

import os
import re

# Tokens that dominate the civics corpus — an overlap made only of these
# says "this text mentions the USA", not "this text relates to this atom".
GENERIC_TOKENS = frozenset({
    "united", "states", "state", "america", "american", "americans",
    "national", "history", "historical", "government", "federal",
    "public", "country", "people", "constitution", "constitutional",
})

DEFAULT_MIN_COSINE = 0.45


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{4,}", (text or "").lower()))


def informative_overlap(hit_text: str, corpus_text: str) -> set[str]:
    return (tokens(hit_text) & tokens(corpus_text)) - GENERIC_TOKENS


def min_cosine() -> float:
    try:
        return float(os.environ.get("JELES_BRIDGE_MIN_COSINE", ""))
    except ValueError:
        pass
    return DEFAULT_MIN_COSINE


def bridge_floor(hit_text: str, corpus_text: str,
                 floor: float | None = None, embed=None) -> dict:
    """Score a candidate serendipity bridge.

    Returns {"passes": bool, "reason": str, "cosine": float | None,
    "overlap": sorted informative tokens}. `embed` is injectable for tests;
    defaults to the Ollama nomic-embed helper in jeles_sources.
    """
    overlap = informative_overlap(hit_text, corpus_text)
    if not overlap:
        return {"passes": False, "reason": "generic-only overlap",
                "cosine": None, "overlap": []}

    if embed is None:
        from core.jeles_sources import _get_embedding as embed
    va, vb = embed(hit_text), embed(corpus_text)
    if not va or not vb:
        return {"passes": False, "reason": "embedder unavailable",
                "cosine": None, "overlap": sorted(overlap)}

    from core.jeles_sources import _cosine
    cos = _cosine(va, vb)
    if floor is None:
        floor = min_cosine()
    if cos < floor:
        return {"passes": False,
                "reason": f"cosine {cos:.2f} below floor {floor:.2f}",
                "cosine": cos, "overlap": sorted(overlap)}
    return {"passes": True, "reason": "ok",
            "cosine": cos, "overlap": sorted(overlap)}
