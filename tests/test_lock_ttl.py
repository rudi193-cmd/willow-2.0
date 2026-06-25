"""Unit tests for stale-lock detection (core.lock_ttl)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.lock_ttl import lock_is_live


def _iso(hours_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def test_unlocked_is_not_live():
    assert lock_is_live({"locked": False}) is False
    assert lock_is_live({}) is False
    assert lock_is_live(None) is False


def test_fresh_lock_is_live():
    assert lock_is_live({"locked": True, "lock_acquired_at": _iso(0.1)}) is True


def test_expired_lock_is_stale():
    # Default TTL is 1h; a lock acquired 8 days ago must read stale.
    assert lock_is_live({"locked": True, "lock_acquired_at": _iso(8 * 24)}) is False


def test_locked_without_timestamp_is_stale():
    # Legacy locks (no lock_acquired_at) cannot be trusted -> self-heal.
    assert lock_is_live({"locked": True}) is False


def test_unparseable_timestamp_is_stale():
    assert lock_is_live({"locked": True, "lock_acquired_at": "not-a-date"}) is False


def test_naive_timestamp_treated_as_utc():
    naive = (datetime.now(timezone.utc) - timedelta(minutes=5)).replace(tzinfo=None)
    assert lock_is_live({"locked": True, "lock_acquired_at": naive.isoformat()}) is True


def test_custom_ttl_boundary():
    ts = _iso(2)
    assert lock_is_live({"locked": True, "lock_acquired_at": ts}, ttl_hours=1.0) is False
    assert lock_is_live({"locked": True, "lock_acquired_at": ts}, ttl_hours=3.0) is True


def test_zulu_suffix_iso_timestamp_is_parsed():
    # Real Z-suffixed ISO (e.g. "2026-06-25T13:15:00Z") must parse via the
    # Z -> +00:00 normalization and read live when fresh.
    z = (datetime.now(timezone.utc) - timedelta(minutes=5)).replace(microsecond=0)
    z_iso = z.isoformat().replace("+00:00", "Z")
    assert lock_is_live({"locked": True, "lock_acquired_at": z_iso}) is True
