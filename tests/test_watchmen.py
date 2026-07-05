"""Tests for core/watchmen.py + the upstream watcher heartbeat write.

The point of the heartbeat is behavioral: a dead loop, a live-but-gh-broken
loop, and a healthy loop must be three distinguishable states in fleet_status.
These tests assert on the real SOIL record and real freshness math — not just
that a call happened.
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.watchmen import (
    DEFAULT_INTERVAL_S,
    STALE_FACTOR,
    WATCHMEN,
    check_watchmen,
    heartbeat_health,
)


@pytest.fixture
def store_root(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path))
    return tmp_path


def _hb(age_s: int, **extra) -> dict:
    at = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    return {"last_tick_at": at.isoformat(), "interval_sec": 900, **extra}


# ── heartbeat_health: freshness math ─────────────────────────────────────────

def test_fresh_heartbeat_is_ok():
    h = heartbeat_health(_hb(age_s=60))
    assert h["status"] == "ok"
    assert 55 <= h["age_s"] <= 70
    assert h["interval_sec"] == 900


def test_heartbeat_older_than_two_intervals_is_stale():
    h = heartbeat_health(_hb(age_s=int(900 * STALE_FACTOR) + 5))
    assert h["status"] == "stale"


def test_heartbeat_just_under_threshold_is_not_stale():
    h = heartbeat_health(_hb(age_s=int(900 * STALE_FACTOR) - 30))
    assert h["status"] == "ok"


def test_missing_record_is_absent():
    assert heartbeat_health(None) == {"status": "absent"}
    assert heartbeat_health({}) == {"status": "absent"}


def test_garbage_timestamp_is_invalid():
    assert heartbeat_health({"last_tick_at": "not-a-date"})["status"] == "invalid"


def test_naive_timestamp_is_treated_as_utc():
    naive = (datetime.now(timezone.utc) - timedelta(seconds=30)).replace(tzinfo=None)
    h = heartbeat_health({"last_tick_at": naive.isoformat(), "interval_sec": 900})
    assert h["status"] == "ok"


def test_bad_interval_falls_back_to_default():
    h = heartbeat_health(_hb(age_s=10) | {"interval_sec": "junk"})
    assert h["interval_sec"] == DEFAULT_INTERVAL_S


# ── heartbeat_health: degraded beats silent-broken ───────────────────────────

def test_fresh_but_gh_broken_is_degraded_not_ok():
    h = heartbeat_health(_hb(age_s=60, gh_ok=False, gh_error="HTTP 401"))
    assert h["status"] == "degraded"
    assert h["gh_ok"] is False
    assert "401" in h["gh_error"]


def test_fresh_but_tick_failed_is_degraded():
    h = heartbeat_health(_hb(age_s=60, tick_ok=False, error="boom"))
    assert h["status"] == "degraded"
    assert h["error"] == "boom"


def test_stale_wins_over_degraded():
    h = heartbeat_health(_hb(age_s=10_000, gh_ok=False))
    assert h["status"] == "stale"


# ── check_watchmen: registry read path ───────────────────────────────────────

def test_check_watchmen_reads_registered_heartbeats():
    fresh = _hb(age_s=5)
    result = check_watchmen(lambda coll, rid: fresh)
    assert set(result) == set(WATCHMEN)
    assert result["upstream_watcher"]["status"] == "ok"


def test_check_watchmen_survives_getter_errors():
    def boom(coll, rid):
        raise RuntimeError("store offline")
    result = check_watchmen(boom)
    assert result["upstream_watcher"]["status"] == "error"
    assert "store offline" in result["upstream_watcher"]["error"]


# ── watcher write → watchmen read, end to end through real SOIL ──────────────

def test_watcher_heartbeat_roundtrips_through_soil(store_root):
    from agents.hanuman.bin import upstream_watcher as uw
    from core import soil

    uw._gh_status.update(ok=False, error="HTTP 401: Bad credentials")
    uw._write_heartbeat(interval_sec=900, tick_ok=True, counts={"new": 3})

    collection, record_id = WATCHMEN["upstream_watcher"]
    record = soil.get(collection, record_id)
    assert record is not None
    assert record["gh_ok"] is False
    assert "401" in record["gh_error"]
    assert record["counts"]["new"] == 3

    health = check_watchmen(soil.get)["upstream_watcher"]
    assert health["status"] == "degraded"  # fresh tick, broken gh — the 401 mode

    uw._gh_status.update(ok=True, error="")
    uw._write_heartbeat(interval_sec=900, tick_ok=True)
    health = check_watchmen(soil.get)["upstream_watcher"]
    assert health["status"] == "ok"


# ── sentinel watchdog (willow-config fleet-dispatch) registration ────────────

def test_sentinel_watchdog_is_registered():
    assert "sentinel_watchdog" in WATCHMEN
    assert WATCHMEN["sentinel_watchdog"] == ("fleet_dispatch/heartbeat",
                                             "sentinel_watchdog")


def test_sentinel_watchdog_heartbeat_roundtrips_through_soil(store_root):
    """The watchdog script lives in willow-config; this pins the contract:
    the record shape it writes classifies correctly through the registry."""
    from datetime import datetime, timezone
    from core import soil

    collection, record_id = WATCHMEN["sentinel_watchdog"]

    # Absent before the first timer run — a never-installed watchdog is
    # visible, not silent.
    assert check_watchmen(soil.get)["sentinel_watchdog"]["status"] == "absent"

    soil.put(collection, record_id, {
        "last_tick_at": datetime.now(timezone.utc).isoformat(),
        "interval_sec": 900,
        "tick_ok": True,
        "counts": {"active_sessions": 2, "missing_sentinel": 0},
    })
    health = check_watchmen(soil.get)["sentinel_watchdog"]
    assert health["status"] == "ok"
    assert health["interval_sec"] == 900

    soil.put(collection, record_id, {
        "last_tick_at": datetime.now(timezone.utc).isoformat(),
        "interval_sec": 900,
        "tick_ok": False,
        "error": "store write failed",
    })
    health = check_watchmen(soil.get)["sentinel_watchdog"]
    assert health["status"] == "degraded"
    assert health["error"] == "store write failed"
