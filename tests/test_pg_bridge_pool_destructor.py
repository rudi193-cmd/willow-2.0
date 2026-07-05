"""PgBridge.__del__ must never touch the connection pool.

GC can fire a destructor while the SAME thread is inside psycopg2's
non-reentrant pool lock (getconn/putconn). A synchronous putconn there
self-deadlocks the thread forever — the recurring ~59% CI pytest-matrix hang
(stack evidence: run 28722927983, getconn → GC → __del__ → putconn).

The fix: destructors enqueue the connection on a lock-free deque; the next
normal-context get_connection() drains it back to the pool.
"""
import gc

import pytest

from core import pg_bridge


@pytest.fixture(autouse=True)
def _clean_orphan_queue():
    pg_bridge._orphaned_conns.clear()
    yield
    pg_bridge._orphaned_conns.clear()


class _SentinelConn:
    def __init__(self):
        self.closed_calls = 0

    def close(self):
        self.closed_calls += 1


def _bridge_with(conn):
    import threading
    bridge = pg_bridge.PgBridge.__new__(pg_bridge.PgBridge)
    bridge._local = threading.local()
    bridge._local.conn = conn
    return bridge


def test_del_enqueues_instead_of_touching_pool(monkeypatch):
    def _forbidden(*a, **kw):
        raise AssertionError("destructor touched the pool")

    monkeypatch.setattr(pg_bridge, "release_connection", _forbidden)
    monkeypatch.setattr(pg_bridge, "_get_pool", _forbidden)

    sentinel = _SentinelConn()
    bridge = _bridge_with(sentinel)

    bridge.__del__()
    del bridge
    gc.collect()

    assert list(pg_bridge._orphaned_conns) == [sentinel]


def test_del_is_idempotent_after_close(monkeypatch):
    released = []
    monkeypatch.setattr(pg_bridge, "release_connection", released.append)

    sentinel = _SentinelConn()
    bridge = _bridge_with(sentinel)
    bridge.close()  # explicit close in normal context still uses the pool

    assert released == [sentinel]
    bridge.__del__()
    assert not pg_bridge._orphaned_conns, "closed bridge must not re-orphan"


def test_get_connection_drains_orphans_first(monkeypatch):
    released = []
    monkeypatch.setattr(pg_bridge, "release_connection", released.append)
    monkeypatch.setattr(pg_bridge, "_cb_check", lambda: True)
    monkeypatch.setattr(pg_bridge, "_pool_warn_if_near_capacity", lambda: None)
    monkeypatch.setattr(pg_bridge, "_connection_alive", lambda c: True)
    monkeypatch.setattr(pg_bridge, "_cb_reset", lambda: None)

    fresh = _SentinelConn()

    class _FakePool:
        def getconn(self):
            return fresh

    monkeypatch.setattr(pg_bridge, "_get_pool", lambda: _FakePool())

    orphan = _SentinelConn()
    pg_bridge._orphaned_conns.append(orphan)

    conn = pg_bridge.get_connection()

    assert conn is fresh
    assert released == [orphan], "orphan must be returned before checkout"
    assert not pg_bridge._orphaned_conns


def test_drain_survives_release_errors(monkeypatch):
    def _boom(conn):
        raise RuntimeError("pool offline")

    monkeypatch.setattr(pg_bridge, "release_connection", _boom)

    orphan = _SentinelConn()
    pg_bridge._orphaned_conns.append(orphan)

    pg_bridge._drain_orphaned_conns()

    assert not pg_bridge._orphaned_conns
    assert orphan.closed_calls == 1, "unreturnable orphan must be closed, not leaked"
