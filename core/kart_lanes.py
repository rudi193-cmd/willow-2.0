"""Kart execution lanes — separate interactive work from long batch jobs.

* ``fast`` — default; drained by ``kart_task_run`` / session ``kart_poll``.
* ``batch`` — long GPU/CPU work; daemon runs when no fast work is pending.
"""
from __future__ import annotations

KART_LANE_FAST = "fast"
KART_LANE_BATCH = "batch"
KART_LANES = (KART_LANE_FAST, KART_LANE_BATCH)


def normalize_lane(lane: str | None) -> str:
    if lane is None or lane == "" or lane == KART_LANE_FAST:
        return KART_LANE_FAST
    if lane == KART_LANE_BATCH:
        return KART_LANE_BATCH
    raise ValueError(f"unknown kart lane: {lane!r} (expected fast|batch)")
