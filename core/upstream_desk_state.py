"""Weekly upstream desk intel scheduling — SOIL state + Kart batch queue."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.lock_ttl import lock_is_live

UPSTREAM_DESK_INTERVAL_DAYS = float(os.environ.get("UPSTREAM_DESK_INTERVAL_DAYS", "7"))
_SOIL_COLLECTION = "upstream_steward/desk_intel"


def upstream_desk_conditions(store) -> dict[str, Any]:
    """Return whether the weekly upstream desk intel run should be queued."""
    state = store.get(_SOIL_COLLECTION, "state") or {}
    if lock_is_live(state):
        return {
            "should_run": False,
            "locked": True,
            "reason": "upstream desk intel already running",
        }

    now = datetime.now(timezone.utc)
    last_str = state.get("last_run_at", "")
    days_elapsed = 999.0
    if last_str:
        try:
            last = datetime.fromisoformat(last_str)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            days_elapsed = (now - last).total_seconds() / 86400
        except Exception:
            pass

    should_run = days_elapsed >= UPSTREAM_DESK_INTERVAL_DAYS
    return {
        "should_run": should_run,
        "days_since_run": round(days_elapsed, 2),
        "last_run_at": last_str or None,
        "interval_days": UPSTREAM_DESK_INTERVAL_DAYS,
        "cold_count": state.get("cold_count"),
        "cold_repos": state.get("cold_repos") or [],
        "reason": (
            f"{days_elapsed:.1f}d elapsed (interval {UPSTREAM_DESK_INTERVAL_DAYS:.0f}d)"
            if should_run
            else f"conditions not met: {days_elapsed:.1f}d / {UPSTREAM_DESK_INTERVAL_DAYS:.0f}d"
        ),
    }


def queue_upstream_desk_task(
    pg,
    *,
    submitted_by: str = "willow",
) -> Optional[str]:
    """Queue scripts/upstream_desk_intel.py via Kart batch lane. Returns task_id or None."""
    root = Path(__file__).resolve().parent.parent
    script = root / "scripts" / "upstream_desk_intel.py"
    cmd = f"cd {root} && {sys.executable} {script} --emit-soil\n# allow_net"
    return pg.submit_task(cmd, submitted_by=submitted_by, agent="kart", lane="batch")


def format_upstream_desk_summary_line(state: dict[str, Any]) -> str:
    """One-line summary for logs / Grove."""
    cold = state.get("cold_count", "?")
    repos = state.get("cold_repos") or []
    sample = ", ".join(repos[:3])
    if len(repos) > 3:
        sample += "…"
    parts = [
        f"upstream desk {state.get('last_run_at', '?')}",
        f"threads={state.get('thread_count', '?')}",
        f"cold={cold}",
    ]
    if sample:
        parts.append(f"cold_repos={sample}")
    return " · ".join(parts)
