"""watchmen.py — heartbeat freshness checks for standing fleet services.
b17: WTCHM  ΔΣ=42

Standing services (upstream watcher, future long-lived loops) write a small
SOIL heartbeat record every tick. This module is the read side: a pure
freshness check plus a registry of known heartbeats, surfaced by
fleet_status so a dead loop is distinguishable from a quiet one.

A loop that ticks but whose upstream dependency fails (e.g. gh auth 401)
reports "degraded", not "ok" — silent-on-success and silent-on-broken-dep
are the two failure modes this exists to catch.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

def get_watchmen() -> dict[str, tuple[str, str]]:
    """Service name → (SOIL collection, record id); derived from the loop registry."""
    try:
        from willow.fylgja.loops.registry import watchmen_targets

        return watchmen_targets()
    except Exception:
        from willow.fylgja.loops.registry import WATCHMEN_SOIL_OVERRIDES

        return dict(WATCHMEN_SOIL_OVERRIDES)

# heartbeat older than STALE_FACTOR × interval ⇒ stale
STALE_FACTOR = 2.0
DEFAULT_INTERVAL_S = 900


def heartbeat_health(record: dict | None, now: datetime | None = None) -> dict:
    """Classify one heartbeat record: ok | degraded | stale | absent | invalid."""
    if not record or not record.get("last_tick_at"):
        return {"status": "absent"}

    now = now or datetime.now(timezone.utc)
    try:
        last = datetime.fromisoformat(str(record["last_tick_at"]))
    except ValueError:
        return {"status": "invalid", "last_tick_at": record.get("last_tick_at")}
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)

    try:
        interval = int(record.get("interval_sec") or DEFAULT_INTERVAL_S)
    except (TypeError, ValueError):
        interval = DEFAULT_INTERVAL_S

    age_s = max(0, int((now - last).total_seconds()))
    stale = age_s > interval * STALE_FACTOR

    out: dict = {
        "status": "stale" if stale else "ok",
        "age_s": age_s,
        "interval_sec": interval,
        "last_tick_at": record["last_tick_at"],
    }
    if not stale and (record.get("gh_ok") is False or record.get("tick_ok") is False):
        out["status"] = "degraded"
    for key in ("tick_ok", "gh_ok"):
        if record.get(key) is False:
            out[key] = False
    for key in ("error", "gh_error"):
        if record.get(key):
            out[key] = str(record[key])[:200]
    return out


def check_watchmen(soil_get: Callable[[str, str], dict | None]) -> dict:
    """Read every registered heartbeat via the provided soil getter."""
    out: dict = {}
    for name, (collection, record_id) in get_watchmen().items():
        try:
            out[name] = heartbeat_health(soil_get(collection, record_id))
        except Exception as exc:
            out[name] = {"status": "error", "error": str(exc)[:200]}
    return out
