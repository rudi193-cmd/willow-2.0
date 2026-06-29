"""Canonical KB lane registry — single source for write-time project enforcement.

The eight lanes below match the 2026-06-29 namespace_reconcile migration
(FRANK ledger namespace_reconcile event). Import here; do not duplicate.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
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

# Fleet identity with god-view reads (scope=*); personas use their home lane.
ORCHESTRATOR_AGENTS: frozenset[str] = frozenset({"willow"})

# Never included in default orchestrator retrieval — grant or explicit project= only.
RESTRICTED_SHAREABLE_LANES: frozenset[str] = frozenset({"personal"})

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


@dataclass(frozen=True)
class LaneReadScope:
    """SQL-level read filter for knowledge.project."""

    projects: Optional[tuple[str, ...]]  # None = no IN clause (all minus exclude)
    exclude: tuple[str, ...] = ()


def lane_read_scope_enabled() -> bool:
    """Allow tests to disable via WILLOW_LANE_READ_SCOPE=0."""
    return os.environ.get("WILLOW_LANE_READ_SCOPE", "1").strip().lower() not in {
        "0", "false", "no", "off",
    }


def agent_read_lane(agent: str) -> str:
    """Home lane for default-deny reads."""
    return AGENT_LANE_ALIASES.get(agent.strip(), agent.strip())


def is_orchestrator_agent(agent: str) -> bool:
    return agent.strip() in ORCHESTRATOR_AGENTS


def _parse_lane_grants() -> dict[str, set[str]]:
    """Optional cross-lane grants: WILLOW_LANE_GRANTS=agent:lane,agent:lane2."""
    raw = os.environ.get("WILLOW_LANE_GRANTS", "").strip()
    grants: dict[str, set[str]] = {}
    if not raw:
        return grants
    for part in raw.split(","):
        part = part.strip()
        if ":" not in part:
            continue
        who, lane = part.split(":", 1)
        lane = lane.strip()
        if lane in CANONICAL_LANES:
            grants.setdefault(who.strip(), set()).add(lane)
    return grants


def can_read_lane(agent: str, lane: str) -> bool:
    """Whether agent may read atoms in lane (grant-gated for cross-lane)."""
    lane = lane.strip()
    if lane not in CANONICAL_LANES:
        return False
    who = agent.strip()
    if is_orchestrator_agent(who):
        return True
    if lane in RESTRICTED_SHAREABLE_LANES:
        return lane in _parse_lane_grants().get(who, set())
    if agent_read_lane(who) == lane:
        return True
    return lane in _parse_lane_grants().get(who, set())


def resolve_lane_read_scope(
    agent: str,
    *,
    scope: str = "",
    project: Optional[str] = None,
) -> LaneReadScope:
    """Default-deny read scope for KB queries.

    - Non-orchestrator agents: home lane only.
    - Orchestrator (willow): all lanes except RESTRICTED_SHAREABLE_LANES.
    - scope='*' (orchestrator only): all lanes including personal.
    - Explicit project= or scope=<lane>: single lane if permitted.
    """
    if not lane_read_scope_enabled():
        return LaneReadScope(projects=None, exclude=())

    who = agent.strip()
    scope_norm = (scope or "").strip().lower()
    proj_raw = (project or "").strip()

    if scope_norm == "*":
        if not is_orchestrator_agent(who):
            return LaneReadScope(projects=(), exclude=())
        return LaneReadScope(projects=None, exclude=())

    target = proj_raw or (
        scope_norm if scope_norm and scope_norm not in ("lane", "") else ""
    )
    if target:
        lane = AGENT_LANE_ALIASES.get(target, target)
        if lane not in CANONICAL_LANES or not can_read_lane(who, lane):
            return LaneReadScope(projects=(), exclude=())
        return LaneReadScope(projects=(lane,), exclude=())

    if is_orchestrator_agent(who):
        return LaneReadScope(
            projects=None,
            exclude=tuple(RESTRICTED_SHAREABLE_LANES),
        )
    return LaneReadScope(projects=(agent_read_lane(who),), exclude=())


def atom_in_lane_scope(atom: dict, lane_scope: LaneReadScope) -> bool:
    proj = (atom.get("project") or "").strip()
    if lane_scope.projects is not None and proj not in lane_scope.projects:
        return False
    return proj not in lane_scope.exclude


def apply_lane_scope_sql(
    filters: list,
    params: list,
    *,
    project: Optional[str] = None,
    lane_scope: Optional[LaneReadScope] = None,
) -> None:
    """Append knowledge.project predicates. Explicit project= wins over lane_scope."""
    if project:
        filters.append("project = %s")
        params.append(project)
        return
    if lane_scope is None:
        return
    if lane_scope.projects is not None:
        if len(lane_scope.projects) == 0:
            filters.append("FALSE")
        elif len(lane_scope.projects) == 1:
            filters.append("project = %s")
            params.append(lane_scope.projects[0])
        else:
            filters.append("project = ANY(%s)")
            params.append(list(lane_scope.projects))
    if lane_scope.exclude:
        filters.append("NOT (project = ANY(%s))")
        params.append(list(lane_scope.exclude))
