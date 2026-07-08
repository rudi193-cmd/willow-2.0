"""Kart execution lanes — separate interactive work from long batch jobs.

* ``fast`` — default; drained by ``kart_task_run`` / session ``kart_poll`` and
  ``kart-worker.service`` (``KART_WORKER_LANE=fast``).
* ``batch`` — long GPU/CPU work; ``kart-worker-batch.service``
  (``KART_WORKER_LANE=batch``) runs concurrently with fast workers.
"""
from __future__ import annotations

import os

KART_LANE_FAST = "fast"
KART_LANE_BATCH = "batch"
KART_LANES = (KART_LANE_FAST, KART_LANE_BATCH)
KART_WORKER_MODE_FAST = "fast"
KART_WORKER_MODE_BATCH = "batch"
KART_WORKER_MODE_ALL = "all"


def normalize_lane(lane: str | None) -> str:
    if lane is None or lane == "" or lane == KART_LANE_FAST:
        return KART_LANE_FAST
    if lane == KART_LANE_BATCH:
        return KART_LANE_BATCH
    raise ValueError(f"unknown kart lane: {lane!r} (expected fast|batch)")


def worker_mode() -> str:
    """Which lane(s) this kart-worker process claims.

    ``fast`` (default) — interactive shell/gh/git; may run N concurrent tasks.
    ``batch`` — one long job at a time (embeds, ingest, GPU).
    ``all`` — legacy single-threaded fast-then-batch (deprecated).
    """
    raw = (os.environ.get("KART_WORKER_LANE") or KART_WORKER_MODE_FAST).strip().lower()
    if raw in (KART_WORKER_MODE_FAST, KART_WORKER_MODE_BATCH, KART_WORKER_MODE_ALL):
        return raw
    raise ValueError(
        f"unknown KART_WORKER_LANE: {raw!r} (expected fast|batch|all)"
    )


def fast_worker_slots() -> int:
    return max(1, int(os.environ.get("KART_FAST_WORKERS", "3")))
