"""Canonical KB lane registry — single source for write-time project enforcement.

The eight lanes below match the 2026-06-29 namespace_reconcile migration
(FRANK ledger namespace_reconcile event). Import here; do not duplicate.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Reconciled lane set (knowledge.project column).
CANONICAL_LANES: frozenset[str] = frozenset({
    "epstein_network",
    "global",
    "heimdallr",
    "personal",
    "rh-dirty",
    "saps1",
    "vishwakarma",
    "willow",
})

ORCHESTRATOR_LANE = "willow"
DEFAULT_LANE = "global"

# Fleet agents merged into the willow orchestrator lane during reconcile.
AGENT_LANE_ALIASES: dict[str, str] = {
    "hanuman": ORCHESTRATOR_LANE,
    "loki": ORCHESTRATOR_LANE,
    "skirnir": ORCHESTRATOR_LANE,
    "vishwakarma": "vishwakarma",
    "heimdallr": "heimdallr",
    "jeles": ORCHESTRATOR_LANE,
    "kart": ORCHESTRATOR_LANE,
    "oakenscroll": ORCHESTRATOR_LANE,
    "willow": ORCHESTRATOR_LANE,
}

# Legacy synthetic graph-artifact namespaces — never mint fresh lanes.
SYNTHETIC_PROJECTS: frozenset[str] = frozenset({
    "dark_matter",
    "revelation",
    "mirror",
    "mycorrhizal",
    "community_detection",
    "synthesis",
    "dream",
})

DERIVED_SOURCE_TYPES: frozenset[str] = frozenset({
    "community_detection",
    "dark_matter",
    "revelation",
    "mirror",
    "mycorrhizal",
    "agent-synthesis",
})


class OffLaneProjectError(ValueError):
    """Raised when knowledge.project is not a canonical lane and cannot be coerced."""


def lane_enforcement_enabled() -> bool:
    """Allow tests to disable via WILLOW_LANE_ENFORCE=0."""
    return os.environ.get("WILLOW_LANE_ENFORCE", "1").strip().lower() not in {
        "0", "false", "no", "off",
    }


def normalize_project(
    project: Optional[str],
    *,
    source_type: Optional[str] = None,
    agent: Optional[str] = None,
) -> str:
    """Coerce a raw project label to a canonical lane.

    Order: agent alias → synthetic namespace → canonical pass-through → hard reject.
    """
    raw = (project or "").strip()
    if not raw and agent:
        raw = agent.strip()
    if not raw:
        raw = DEFAULT_LANE

    if not lane_enforcement_enabled():
        return raw

    lane = AGENT_LANE_ALIASES.get(raw, raw)

    if lane in SYNTHETIC_PROJECTS:
        logger.info("lane_enforce: synthetic project %r → %s", raw, ORCHESTRATOR_LANE)
        return ORCHESTRATOR_LANE

    if source_type in DERIVED_SOURCE_TYPES and lane not in CANONICAL_LANES:
        logger.info(
            "lane_enforce: derived source_type=%r project=%r → %s",
            source_type, raw, ORCHESTRATOR_LANE,
        )
        return ORCHESTRATOR_LANE

    if lane in CANONICAL_LANES:
        return lane

    raise OffLaneProjectError(
        f"project {raw!r} is not a canonical lane "
        f"({', '.join(sorted(CANONICAL_LANES))})"
    )
