"""Circuit-breaker tests for core.pg_bridge.get_connection.

Pure-logic + mock tests — no live Postgres required (unlike test_pg_bridge.py,
which asserts schema against a real DB).

Audited 2026-06-15 (PR #396, Dimension 2): get_connection funnels every DB
operation in the fleet and its circuit-breaker had no direct test. The breaker
is the protection that matters for the PR #393 failure mode (connection-pool
exhaustion when Postgres is degraded) — when the circuit is OPEN, get_connection
must fail fast and NOT ask the pool for another connection. test_fail_fast_when_open
is that regression guard.
"""
import pytest

from core import pg_bridge


@pytest.fixture(autouse=True)
def _reset_breaker():
    """Breaker state is module-global; reset before and after every test."""
    pg_bridge._cb_reset()
    yield
    pg_bridge._cb_reset()


# ── Breaker state machine ─────────────────────────────────────────────────────

def test_circuit_opens_after_threshold_failures():
    for _ in range(pg_bridge._CB_THRESHOLD):
        pg_bridge._cb_record_failure()
    assert pg_bridge._cb_check() is False
    assert pg_bridge.cb_state()["status"] == "open"


def test_circuit_stays_closed_below_threshold():
    for _ in range(pg_bridge._CB_THRESHOLD - 1):
        pg_bridge._cb_record_failure()
    assert pg_bridge._cb_check() is True
    assert pg_bridge.cb_state()["status"] == "closed"


def test_reset_closes_an_open_circuit():
    for _ in range(pg_bridge._CB_THRESHOLD):
        pg_bridge._cb_record_failure()
    assert pg_bridge._cb_check() is False
    pg_bridge._cb_reset()
    assert pg_bridge._cb_check() is True
    assert pg_bridge.cb_state()["recent_failures"] == 0


def test_circuit_half_opens_after_reset_window(monkeypatch):
    """Once _CB_RESET seconds elapse, the breaker allows a probe again."""
    clock = {"t": 1000.0}
    monkeypatch.setattr(pg_bridge.time, "monotonic", lambda: clock["t"])
    for _ in range(pg_bridge._CB_THRESHOLD):
        pg_bridge._cb_record_failure()
    assert pg_bridge._cb_check() is False  # open immediately after tripping
    clock["t"] += pg_bridge._CB_RESET + 1  # advance past the backoff window
    assert pg_bridge._cb_check() is True   # half-open: a probe is allowed


def test_stale_failures_outside_window_are_pruned(monkeypatch):
    """Failures older than _CB_WINDOW do not count toward the threshold."""
    clock = {"t": 1000.0}
    monkeypatch.setattr(pg_bridge.time, "monotonic", lambda: clock["t"])
    # Two old failures, then jump past the window so they age out.
    pg_bridge._cb_record_failure()
    pg_bridge._cb_record_failure()
    clock["t"] += pg_bridge._CB_WINDOW + 1
    # A single fresh failure must not trip a threshold-3 breaker on its own.
    pg_bridge._cb_record_failure()
    assert pg_bridge._cb_check() is True
    assert pg_bridge.cb_state()["recent_failures"] == 1


# ── get_connection integration with the breaker ───────────────────────────────

def test_get_connection_fails_fast_when_circuit_open(monkeypatch):
    """REGRESSION (PR #393): an open circuit must raise WITHOUT touching the pool."""
    for _ in range(pg_bridge._CB_THRESHOLD):
        pg_bridge._cb_record_failure()

    def _must_not_be_called():
        raise AssertionError("pool must not be consulted while circuit is open")

    monkeypatch.setattr(pg_bridge, "_get_pool", _must_not_be_called)
    with pytest.raises(RuntimeError, match="circuit open"):
        pg_bridge.get_connection()


def test_get_connection_success_resets_breaker(monkeypatch):
    """A successful checkout clears accumulated (sub-threshold) failures."""
    pg_bridge._cb_record_failure()
    pg_bridge._cb_record_failure()
    assert pg_bridge.cb_state()["recent_failures"] == 2

    alive = _AliveConn()
    monkeypatch.setattr(pg_bridge, "_get_pool", lambda: _FakePool(alive))

    conn = pg_bridge.get_connection()
    assert conn is alive
    assert pg_bridge.cb_state()["recent_failures"] == 0


def test_get_connection_discards_stale_pool_checkout(monkeypatch):
    """Dead pooled connections are discarded instead of handed to callers."""
    alive = _AliveConn()
    pool = _StaleThenAlivePool(_StaleConn(), alive)
    monkeypatch.setattr(pg_bridge, "_get_pool", lambda: pool)

    conn = pg_bridge.get_connection()
    assert conn is alive
    assert pool.discarded == 1


def test_get_connection_falls_back_to_direct_connect(monkeypatch):
    """Pool failure falls back to a direct connect; success still resets."""
    pg_bridge._cb_record_failure()
    sentinel = object()
    monkeypatch.setattr(pg_bridge, "_get_pool", lambda: _RaisingPool())
    monkeypatch.setattr(pg_bridge, "_connect", lambda: sentinel)

    conn = pg_bridge.get_connection()
    assert conn is sentinel
    assert pg_bridge.cb_state()["recent_failures"] == 0


def test_get_connection_records_failure_when_both_paths_fail(monkeypatch):
    """Pool AND direct connect failing records one breaker failure and re-raises."""
    monkeypatch.setattr(pg_bridge, "_get_pool", lambda: _RaisingPool())

    def _boom():
        raise OSError("postgres unreachable")

    monkeypatch.setattr(pg_bridge, "_connect", _boom)
    before = pg_bridge.cb_state()["recent_failures"]
    with pytest.raises(OSError, match="postgres unreachable"):
        pg_bridge.get_connection()
    assert pg_bridge.cb_state()["recent_failures"] == before + 1


def test_repeated_connect_failures_trip_the_breaker(monkeypatch):
    """Enough get_connection failures open the circuit — then it fails fast."""
    monkeypatch.setattr(pg_bridge, "_get_pool", lambda: _RaisingPool())
    monkeypatch.setattr(pg_bridge, "_connect", _boom_connect)

    for _ in range(pg_bridge._CB_THRESHOLD):
        with pytest.raises(OSError):
            pg_bridge.get_connection()

    # Circuit is now open: the next call fails fast with the breaker message,
    # not the underlying connect error.
    with pytest.raises(RuntimeError, match="circuit open"):
        pg_bridge.get_connection()


# ── helpers ───────────────────────────────────────────────────────────────────

class _AliveConn:
    """Minimal stand-in that passes pg_bridge._connection_alive()."""

    closed = 0

    class info:
        transaction_status = 0

    def rollback(self):
        pass

    def cursor(self):
        return _AliveCursor()


class _AliveCursor:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def execute(self, _sql):
        pass


class _StaleConn:
    closed = 1

    class info:
        transaction_status = 0


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def getconn(self):
        return self._conn

    def putconn(self, conn, close=False):
        pass


class _StaleThenAlivePool:
    def __init__(self, stale, alive):
        self._stale = stale
        self._alive = alive
        self.discarded = 0

    def getconn(self):
        if self.discarded == 0:
            return self._stale
        return self._alive

    def putconn(self, conn, close=False):
        if close:
            self.discarded += 1


class _RaisingPool:
    def getconn(self):
        raise RuntimeError("pool exhausted")


def _boom_connect():
    raise OSError("postgres unreachable")
