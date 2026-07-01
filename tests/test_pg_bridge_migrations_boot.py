"""Boot-time migration + submit_task logging for core.pg_bridge.

Mock tests — no live Postgres required.
"""
import logging
import threading
from unittest.mock import MagicMock

import pytest

from core import pg_bridge


def _close_pool():
    pool = pg_bridge._pool
    if pool is not None:
        try:
            pool.closeall()
        except Exception:
            pass
    pg_bridge._pool = None


@pytest.fixture(autouse=True)
def _reset_pool():
    _close_pool()
    yield
    _close_pool()


class _FakeCursor:
    def __init__(self, schema_exists: bool):
        self._schema_exists = schema_exists

    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return (1,) if self._schema_exists else None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _FakeConn:
    def __init__(self, schema_exists: bool):
        self._schema_exists = schema_exists

    def cursor(self, *args, **kwargs):
        return _FakeCursor(self._schema_exists)

    def rollback(self):
        pass

    def commit(self):
        pass


class _FakePool:
    def __init__(self, schema_exists: bool):
        self._schema_exists = schema_exists

    def getconn(self):
        return _FakeConn(self._schema_exists)

    def putconn(self, conn):
        pass


def test_get_pool_existing_schema_runs_migrations(monkeypatch):
    calls = {"migrations": 0, "init": 0}

    def _run_migrations(conn):
        calls["migrations"] += 1

    def _init_schema(conn):
        calls["init"] += 1

    monkeypatch.setattr(pg_bridge, "run_migrations", _run_migrations)
    monkeypatch.setattr(pg_bridge, "init_schema", _init_schema)
    monkeypatch.delenv("WILLOW_PG_SKIP_SCHEMA_INIT", raising=False)

    import psycopg2.pool

    monkeypatch.setattr(
        psycopg2.pool,
        "ThreadedConnectionPool",
        lambda **kw: _FakePool(schema_exists=True),
    )

    pg_bridge._get_pool()
    assert calls["migrations"] == 1
    assert calls["init"] == 0


def test_get_pool_fresh_schema_runs_init_schema(monkeypatch):
    calls = {"migrations": 0, "init": 0}

    monkeypatch.setattr(pg_bridge, "run_migrations", lambda c: calls.__setitem__("migrations", calls["migrations"] + 1))
    monkeypatch.setattr(pg_bridge, "init_schema", lambda c: calls.__setitem__("init", calls["init"] + 1))
    monkeypatch.delenv("WILLOW_PG_SKIP_SCHEMA_INIT", raising=False)

    import psycopg2.pool

    monkeypatch.setattr(
        psycopg2.pool,
        "ThreadedConnectionPool",
        lambda **kw: _FakePool(schema_exists=False),
    )

    pg_bridge._get_pool()
    assert calls["init"] == 1
    assert calls["migrations"] == 0


def test_submit_task_logs_insert_failure(caplog, monkeypatch):
    bridge = pg_bridge.PgBridge.__new__(pg_bridge.PgBridge)
    bridge._local = threading.local()
    mock_conn = MagicMock()
    mock_conn.closed = False
    cur = MagicMock()
    cur.execute.side_effect = Exception("column submitter_run_id does not exist")
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cur)
    cm.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = cm
    bridge.conn = mock_conn
    bridge.gen_id = MagicMock(return_value="ABCD1234")
    monkeypatch.setattr(bridge, "_ensure_conn", lambda: None)

    with caplog.at_level(logging.WARNING, logger="core.pg_bridge"):
        result = bridge.submit_task("echo hi", submitted_by="willow", submitter_run_id="run-1")

    assert result is None
    assert any("submit_task failed" in r.message for r in caplog.records)


class _StatefulCursor:
    def __init__(self, conn):
        self._conn = conn
        self._last = ""

    def execute(self, sql, params=None):
        self._last = sql
        self._conn.executed.append(sql)

    def fetchone(self):
        if "information_schema.tables" in self._last:
            return (1,)
        if "schema_migrations_state" in self._last:
            return (self._conn.stored_hash,) if self._conn.stored_hash else None
        return None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _StatefulConn:
    def __init__(self, stored_hash):
        self.stored_hash = stored_hash
        self.executed = []

    def cursor(self, *args, **kwargs):
        return _StatefulCursor(self)

    def rollback(self):
        pass

    def commit(self):
        pass


class _StatefulPool:
    def __init__(self, conn):
        self._conn = conn

    def getconn(self):
        return self._conn

    def putconn(self, conn):
        pass


def _arm_pool(monkeypatch, conn):
    import psycopg2.pool

    monkeypatch.delenv("WILLOW_PG_SKIP_SCHEMA_INIT", raising=False)
    monkeypatch.setattr(
        psycopg2.pool, "ThreadedConnectionPool", lambda **kw: _StatefulPool(conn)
    )


def test_get_pool_skips_migrations_when_fingerprint_current(monkeypatch):
    calls = {"migrations": 0}
    monkeypatch.setattr(
        pg_bridge, "run_migrations",
        lambda c: calls.__setitem__("migrations", calls["migrations"] + 1),
    )
    conn = _StatefulConn(stored_hash=pg_bridge._MIGRATIONS_FINGERPRINT)
    _arm_pool(monkeypatch, conn)
    pg_bridge._get_pool()
    assert calls["migrations"] == 0


def test_get_pool_runs_and_records_when_fingerprint_stale(monkeypatch):
    calls = {"migrations": 0}
    monkeypatch.setattr(
        pg_bridge, "run_migrations",
        lambda c: calls.__setitem__("migrations", calls["migrations"] + 1),
    )
    conn = _StatefulConn(stored_hash="stale-fingerprint")
    _arm_pool(monkeypatch, conn)
    pg_bridge._get_pool()
    assert calls["migrations"] == 1
    assert any("ON CONFLICT (id) DO UPDATE" in s for s in conn.executed)
