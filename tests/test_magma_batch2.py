"""Magma-layer batch 2 effect tests.

Covers three silent resource leaks found in the 2026-07-05 audit:
- PgBridge.__del__ orphaned only the GC thread's conn; other threads'
  checkouts leaked pool slots (post-#697 residual).
- EdgeLinker.close() destroyed the pooled connection instead of returning it.
- SoilClient.close() could stop its loop before closing the exit stack,
  orphaning the spawned willow.sh child.
"""
import asyncio
import threading
import time

import pytest

from core import pg_bridge
from willow.hooks.edge_linking import EdgeLinker


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


def _tracked_bridge():
    bridge = pg_bridge.PgBridge.__new__(pg_bridge.PgBridge)
    bridge._local = threading.local()
    bridge._outstanding = {}
    return bridge


# ── PgBridge cross-thread orphaning ──────────────────────────────────────────

def test_conn_setter_tracks_checkouts():
    bridge = _tracked_bridge()
    conn = _SentinelConn()
    bridge.conn = conn
    thread, tracked = bridge._outstanding[id(conn)]
    assert tracked is conn
    assert thread is threading.current_thread()


def test_reap_returns_dead_threads_conns(monkeypatch):
    """A thread that exited must have its conn released, not pinned forever.

    This is the regression CI caught on the first push: pinning 100 dead
    workers' conns exhausted Postgres max_connections.
    """
    released = []
    monkeypatch.setattr(pg_bridge, "release_connection", released.append)

    bridge = _tracked_bridge()
    worker_conn = _SentinelConn()

    def _worker():
        bridge.conn = worker_conn

    t = threading.Thread(target=_worker)
    t.start()
    t.join()  # thread is now dead; its checkout is still tracked

    bridge._reap_dead_thread_conns()

    assert released == [worker_conn], "dead thread's conn must return to the pool"
    assert id(worker_conn) not in bridge._outstanding
    # Live thread's conn must never be reaped.
    live_conn = _SentinelConn()
    bridge.conn = live_conn
    bridge._reap_dead_thread_conns()
    assert id(live_conn) in bridge._outstanding


def test_del_orphans_conns_from_all_threads(monkeypatch):
    def _forbidden(*a, **kw):
        raise AssertionError("destructor touched the pool")

    monkeypatch.setattr(pg_bridge, "release_connection", _forbidden)
    monkeypatch.setattr(pg_bridge, "_get_pool", _forbidden)

    bridge = _tracked_bridge()
    main_conn = _SentinelConn()
    bridge.conn = main_conn

    worker_conn = _SentinelConn()

    def _worker():
        bridge.conn = worker_conn  # thread-local slot invisible to main thread

    t = threading.Thread(target=_worker)
    t.start()
    t.join()

    # Sanity: main thread's local only sees its own conn — the old __del__
    # could therefore never reach worker_conn.
    assert bridge.conn is main_conn

    bridge.__del__()
    assert main_conn in pg_bridge._orphaned_conns
    assert worker_conn in pg_bridge._orphaned_conns, (
        "cross-thread checkout leaked: only the GC thread's conn was orphaned"
    )

    bridge.__del__()  # second GC call must not double-enqueue
    assert list(pg_bridge._orphaned_conns).count(main_conn) == 1
    assert list(pg_bridge._orphaned_conns).count(worker_conn) == 1


def test_close_untracks_so_del_cannot_double_release(monkeypatch):
    released = []
    monkeypatch.setattr(pg_bridge, "release_connection", released.append)

    bridge = _tracked_bridge()
    conn = _SentinelConn()
    bridge.conn = conn
    bridge.close()

    assert released == [conn]
    bridge.__del__()
    assert conn not in pg_bridge._orphaned_conns, (
        "closed conn re-orphaned — would double-putconn and corrupt the pool"
    )


def test_legacy_shaped_bridge_still_orphans_local_conn():
    """Instances without the tracking map keep the old thread-local behavior."""
    bridge = pg_bridge.PgBridge.__new__(pg_bridge.PgBridge)
    bridge._local = threading.local()
    conn = _SentinelConn()
    bridge._local.conn = conn

    bridge.__del__()
    assert conn in pg_bridge._orphaned_conns


# ── EdgeLinker pooled-connection release ─────────────────────────────────────

def test_edge_linker_close_returns_conn_to_pool_not_socket_close():
    class _FakeBridge:
        def __init__(self):
            self.conn = _SentinelConn()
            self.close_calls = 0

        def close(self):
            self.close_calls += 1

    linker = EdgeLinker.__new__(EdgeLinker)
    linker.bridge = _FakeBridge()

    linker.close()

    assert linker.bridge.close_calls == 1
    assert linker.bridge.conn.closed_calls == 0, (
        "conn.close() destroys a checked-out pooled connection — slot leak"
    )


# ── SoilClient shutdown ordering ─────────────────────────────────────────────

def _soil_client_with_loop():
    from sap.clients.soil_client import SoilClient

    client = SoilClient.__new__(SoilClient)
    client._app_id = "test"
    client._available = True
    client._session = object()
    client._loop = asyncio.new_event_loop()
    client._thread = threading.Thread(
        target=client._loop.run_forever, daemon=True, name="soil-test-loop"
    )
    client._thread.start()
    return client


class _RecordingExitStack:
    def __init__(self):
        self.aclosed = threading.Event()

    async def aclose(self):
        self.aclosed.set()


def test_soil_close_acloses_stack_before_stopping_loop():
    client = _soil_client_with_loop()
    stack = _RecordingExitStack()
    client._exit_stack = stack

    client.close(timeout=5.0)

    assert stack.aclosed.is_set(), (
        "loop stopped without closing the exit stack — willow.sh child orphaned"
    )
    client._thread.join(timeout=2)
    assert not client._thread.is_alive()
    assert client._loop.is_closed(), "event loop leaked after blocking close"
    assert client._available is False


def test_soil_close_is_idempotent():
    client = _soil_client_with_loop()
    client._exit_stack = _RecordingExitStack()
    client.close(timeout=5.0)
    client.close(timeout=5.0)  # second call: loop no longer running → no-op
    client.__del__()  # and GC after close must be a clean no-op too


def test_soil_close_from_loop_thread_does_not_deadlock():
    """GC on the loop thread must fire-and-forget, not block on its own loop."""
    client = _soil_client_with_loop()
    stack = _RecordingExitStack()
    client._exit_stack = stack

    done = threading.Event()
    elapsed = {}

    def _on_loop():
        start = time.monotonic()
        client.close(timeout=5.0)  # runs ON the loop thread
        elapsed["s"] = time.monotonic() - start
        done.set()

    client._loop.call_soon_threadsafe(_on_loop)

    assert done.wait(timeout=3), "close() deadlocked on the loop thread"
    assert elapsed["s"] < 1.0, f"close() blocked {elapsed['s']:.2f}s on loop thread"
    assert stack.aclosed.wait(timeout=2), "exit stack never closed"
    client._thread.join(timeout=2)
    assert not client._thread.is_alive(), "loop never stopped after shutdown"
