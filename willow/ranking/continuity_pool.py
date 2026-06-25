"""Curated retrieval pool for continuity-oriented KB search.

WCE source-type sweep (2026-06-25): B2 (handoff+KB+external) minus ``intake``
lifts cold-relevant recall ~+30% vs the full non-LoCoMo table while warm recall
stays flat. Scope: boot/cold-recovery/WCE continuity paths — not general search.
"""
from __future__ import annotations

import os
from typing import Optional

# Mirror willow/bench/continuity/run_wce.py LAYER_* (B0-B3 taxonomy).
_LAYER_HANDOFF = ("session", "session_promote", "hook_stop", "handoff")
_LAYER_KB_ADD = (
    "mcp", "revelation", "intake", "seed", "dark_matter",
    "agent-synthesis", "community_detection", "mycorrhizal",
    "norn_pass", "drift-resolve", "nest-seed", "discovered_pattern", "think_map",
)
_LAYER_EXTERNAL_ADD = (
    "external", "fetched", "literature", "web_search",
    "ai_news", "repo_doc", "public-demo",
)
_CURATED_EXCLUDE = frozenset({"intake"})


def b2_source_types() -> list[str]:
    """B2 layer: handoff + KB + external (no long-tail eval types)."""
    handoff = list(dict.fromkeys(_LAYER_HANDOFF))
    kb = list(dict.fromkeys(handoff + list(_LAYER_KB_ADD)))
    return list(dict.fromkeys(kb + list(_LAYER_EXTERNAL_ADD)))


def curated_continuity_source_types() -> list[str]:
    """B2 minus intake — WCE leave-one-out winner for cold-relevant recall."""
    return [s for s in b2_source_types() if s not in _CURATED_EXCLUDE]


def resolve_continuity_source_types(*, pool: Optional[str] = None) -> Optional[list[str]]:
    """Source-type allow-list for continuity retrieval, or None for full table.

    pool / WILLOW_CONTINUITY_POOL:
      curated (default) — B2 minus intake
      full | off        — no source_type filter
    """
    mode = (pool or os.environ.get("WILLOW_CONTINUITY_POOL", "curated")).strip().lower()
    if mode in ("full", "off", "none"):
        return None
    if mode == "curated":
        return curated_continuity_source_types()
    raise ValueError(f"unknown continuity pool {mode!r} — use curated|full|off")
