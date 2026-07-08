"""Shared SOIL heartbeat writer for loop-registry watchmen (ADR bite 6).

Daemons and timers call write() or write_throttled() so fleet_status can
distinguish a dead loop from a quiet one via core.watchmen.check_watchmen.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

logger = logging.getLogger("loop_heartbeat")

_last_mono: dict[str, float] = {}
_DEFAULT_INTERVAL_S = 900


def interval_sec_for(watchmen_key: str) -> int:
    """Resolve heartbeat.interval_sec from loops.json for watchmen_key."""
    try:
        from willow.fylgja.loops.registry import load_registry

        for loop in load_registry():
            hb = loop.get("heartbeat") or {}
            if str(hb.get("watchmen_key") or "").strip() == watchmen_key:
                return int(hb.get("interval_sec") or _DEFAULT_INTERVAL_S)
    except Exception:
        pass
    return _DEFAULT_INTERVAL_S


def resolve_soil(watchmen_key: str) -> tuple[str, str]:
    from willow.fylgja.loops.registry import watchmen_targets

    return watchmen_targets()[watchmen_key]


def write(
    watchmen_key: str,
    *,
    tick_ok: bool = True,
    interval_sec: int | None = None,
    **extra,
) -> bool:
    """Write one heartbeat record. Returns False on lookup or SOIL errors."""
    try:
        from core import soil

        collection, record_id = resolve_soil(watchmen_key)
        interval = interval_sec if interval_sec is not None else interval_sec_for(watchmen_key)
        soil.put(
            collection,
            record_id,
            {
                "last_tick_at": datetime.now(timezone.utc).isoformat(),
                "interval_sec": interval,
                "tick_ok": tick_ok,
                "pid": os.getpid(),
                **extra,
            },
        )
        return True
    except Exception as exc:
        logger.debug("heartbeat write skipped for %s: %s", watchmen_key, exc)
        return False


def write_throttled(watchmen_key: str, *, tick_ok: bool = True, **extra) -> bool:
    """Write at most once per registry interval_sec (per process, per key)."""
    interval = interval_sec_for(watchmen_key)
    now = time.monotonic()
    last = _last_mono.get(watchmen_key, 0.0)
    if last and (now - last) < interval:
        return False
    if write(watchmen_key, tick_ok=tick_ok, interval_sec=interval, **extra):
        _last_mono[watchmen_key] = now
        return True
    return False


def reset_throttle(watchmen_key: str = "") -> None:
    """Test helper — clear throttle state for one key or all keys."""
    if watchmen_key:
        _last_mono.pop(watchmen_key, None)
    else:
        _last_mono.clear()
