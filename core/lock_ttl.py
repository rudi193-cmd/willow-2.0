"""Stale-lock detection for sticky SOIL state locks (dream, WCE witness).

A run acquires its lock by writing ``{"locked": True, "lock_acquired_at": <iso>}``
to its SOIL state and releases it on completion (success or handled error). A
*hard* kill — SIGKILL from the Kart daemon timeout, a reboot, an OOM — skips both
release paths and strands the lock forever. With no TTL, every later condition
check short-circuits on ``locked: True`` and the routine never runs again.

``lock_is_live`` treats a lock as held only while it is fresh. A lock whose
``lock_acquired_at`` is older than the TTL, missing, or unparseable is reported
stale so callers fall through and self-heal a crashed predecessor.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

DEFAULT_LOCK_TTL_HOURS = float(os.environ.get("WILLOW_LOCK_TTL_HOURS", "1.0"))


def lock_is_live(
    state: dict[str, Any] | None,
    ttl_hours: float = DEFAULT_LOCK_TTL_HOURS,
    ts_key: str = "lock_acquired_at",
) -> bool:
    """Return True only if *state* holds an active (non-stale) lock.

    A lock is live when ``locked`` is truthy AND ``ts_key`` is a parseable
    timestamp within ``ttl_hours``. A truthy ``locked`` with a missing, invalid,
    or expired timestamp is treated as a stranded lock from a crashed run and
    reported not-live, so the caller proceeds and reclaims it.
    """
    if not state or not state.get("locked"):
        return False
    ts = state.get(ts_key)
    if not ts:
        return False
    try:
        acquired = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False
    if acquired.tzinfo is None:
        acquired = acquired.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - acquired).total_seconds() / 3600
    return age_hours < ttl_hours
