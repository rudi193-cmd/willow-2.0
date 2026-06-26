"""Tests for core.dream_state.dream_conditions.

The dream gate counts "sessions since last dream" from willow.runs. Kart shell
tasks also open willow.runs rows (purpose='kart:...', one per task), so the
count must exclude them or it inflates ~16x and the gate's reported number lies.
These tests use fakes — no live Postgres — so they run in CI.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.dream_state import dream_conditions


class FakeCursor:
    def __init__(self, count: int):
        self._count = count
        self.executed: list[tuple[str, tuple]] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params or ()))

    def fetchone(self):
        return (self._count,)


class FakeConn:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class FakePG:
    def __init__(self, count: int):
        self._cursor = FakeCursor(count)
        self.conn = FakeConn(self._cursor)

    def _ensure_conn(self):
        pass


class FakeStore:
    """Returns a dream state with a configurable last_dream_at and no live lock."""

    def __init__(self, last_dream_at: str | None):
        self._last = last_dream_at

    def get(self, collection, key):
        return {"last_dream_at": self._last} if self._last else {}


def _hours_ago(h: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat()


def test_query_excludes_kart_runs_with_last_dream():
    pg = FakePG(count=15)
    store = FakeStore(_hours_ago(30))
    dream_conditions("willow", store, pg)
    sql, params = pg._cursor.executed[-1]
    assert "NOT LIKE 'kart:%%'" in sql
    assert "started_at > %s" in sql
    assert params[0] == "willow"


def test_query_excludes_kart_runs_without_last_dream():
    pg = FakePG(count=3)
    store = FakeStore(None)  # never dreamed
    dream_conditions("willow", store, pg)
    sql, _ = pg._cursor.executed[-1]
    assert "NOT LIKE 'kart:%%'" in sql
    # no time bound when there's no prior dream
    assert "started_at > %s" not in sql


def test_should_dream_true_above_thresholds():
    # 30h elapsed, 15 real sessions -> both gates pass
    res = dream_conditions("willow", FakeStore(_hours_ago(30)), FakePG(count=15))
    assert res["should_dream"] is True
    assert res["sessions_since_dream"] == 15


def test_no_dream_when_too_few_sessions():
    # plenty of time, but only 4 sessions -> below the 5-session gate
    res = dream_conditions("willow", FakeStore(_hours_ago(48)), FakePG(count=4))
    assert res["should_dream"] is False
    assert res["sessions_since_dream"] == 4


def test_no_dream_when_too_recent():
    # 10 sessions but only 2h since last dream -> below the 24h gate
    res = dream_conditions("willow", FakeStore(_hours_ago(2)), FakePG(count=10))
    assert res["should_dream"] is False


def test_live_lock_blocks():
    store = FakeStore(_hours_ago(30))
    # override get to return a fresh lock
    store.get = lambda c, k: {
        "last_dream_at": _hours_ago(30),
        "locked": True,
        "lock_acquired_at": _hours_ago(0.1),
    }
    res = dream_conditions("willow", store, FakePG(count=15))
    assert res["should_dream"] is False
    assert res.get("locked") is True
