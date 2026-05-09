"""tests/test_run_ledger.py — Unit tests for core.run_ledger (Run Ledger v0).

Schema is applied here because the migration is not in init_schema yet.
Uses willow_19_test (from conftest) like every other test in this suite.
"""
import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

_DB   = "willow_19_test"
_USER = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))


def _connect():
    import psycopg2
    return psycopg2.connect(dbname=_DB, user=_USER)


@pytest.fixture(scope="module", autouse=True)
def run_ledger_schema():
    """Ensure willow.runs tables exist in the test database."""
    conn = _connect()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS willow")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS willow.runs (
                id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
                parent_run_id   uuid        REFERENCES willow.runs(id),
                purpose         text,
                initiator       text        NOT NULL,
                repo_roots      text[]      DEFAULT '{}',
                status          text        NOT NULL DEFAULT 'running'
                                            CHECK (status IN ('running','completed','abandoned','crashed')),
                started_at      timestamptz NOT NULL DEFAULT now(),
                ended_at        timestamptz
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS willow.run_agents (
                run_id      uuid        NOT NULL REFERENCES willow.runs(id) ON DELETE CASCADE,
                agent       text        NOT NULL,
                joined_at   timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY (run_id, agent)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS willow.run_events (
                id          bigserial   PRIMARY KEY,
                run_id      uuid        NOT NULL REFERENCES willow.runs(id) ON DELETE CASCADE,
                agent       text        NOT NULL,
                event_type  text        NOT NULL,
                ref         text,
                ts          timestamptz NOT NULL DEFAULT now()
            )
        """)
    conn.close()
    yield
    # Teardown: clean all test rows
    conn = _connect()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("TRUNCATE willow.run_events, willow.run_agents, willow.runs CASCADE")
    conn.close()


@pytest.fixture(autouse=True)
def clean_tmp_file():
    """Remove the agent tmp file before and after each test."""
    tmp = Path("/tmp/willow-run-test_agent.json")
    tmp.unlink(missing_ok=True)
    yield
    tmp.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def patch_run_ledger_env(monkeypatch):
    monkeypatch.setenv("WILLOW_PG_DB", _DB)
    monkeypatch.setenv("WILLOW_AGENT_NAME", "test_agent")


# ── import after env is patched ────────────────────────────────────────────

import importlib
import core.run_ledger as _rl_mod


@pytest.fixture(autouse=True)
def reload_module(patch_run_ledger_env):
    importlib.reload(_rl_mod)


# ── open_run ───────────────────────────────────────────────────────────────

def test_open_run_returns_uuid():
    run_id = _rl_mod.open_run(purpose="test open_run")
    assert isinstance(run_id, str)
    assert len(run_id) == 36  # uuid4 format


def test_open_run_creates_db_row():
    run_id = _rl_mod.open_run(purpose="test db row")
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute("SELECT status, initiator FROM willow.runs WHERE id = %s", (run_id,))
        row = cur.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "running"
    assert row[1] == "test_agent"


def test_open_run_writes_tmp_file():
    _rl_mod.open_run(purpose="test tmp file")
    tmp = Path("/tmp/willow-run-test_agent.json")
    assert tmp.exists()


def test_open_run_tmp_file_contains_run_id():
    import json
    run_id = _rl_mod.open_run(purpose="test tmp content")
    tmp = Path("/tmp/willow-run-test_agent.json")
    data = json.loads(tmp.read_text())
    assert data.get("run_id") == run_id


# ── current_run_id ─────────────────────────────────────────────────────────

def test_current_run_id_returns_none_without_tmp():
    assert _rl_mod.current_run_id() is None


def test_current_run_id_returns_opened_run():
    run_id = _rl_mod.open_run(purpose="test current_run_id")
    assert _rl_mod.current_run_id() == run_id


# ── close_run ──────────────────────────────────────────────────────────────

def test_close_run_sets_status_completed():
    run_id = _rl_mod.open_run(purpose="test close completed")
    _rl_mod.close_run("completed")
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM willow.runs WHERE id = %s", (run_id,))
        row = cur.fetchone()
    conn.close()
    assert row[0] == "completed"


def test_close_run_clears_tmp_file():
    _rl_mod.open_run(purpose="test close clears tmp")
    _rl_mod.close_run("completed")
    assert not Path("/tmp/willow-run-test_agent.json").exists()


def test_close_run_noops_without_open_run():
    _rl_mod.close_run("completed")  # should not raise


# ── log_event ─────────────────────────────────────────────────────────────

def test_log_event_inserts_row():
    run_id = _rl_mod.open_run(purpose="test log_event")
    _rl_mod.log_event("task_submit", ref="ABCD1234")
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT event_type, ref FROM willow.run_events WHERE run_id = %s",
            (run_id,),
        )
        rows = cur.fetchall()
    conn.close()
    assert any(r[0] == "task_submit" and r[1] == "ABCD1234" for r in rows)


def test_log_event_noops_without_open_run():
    _rl_mod.log_event("task_submit", ref="NO_RUN")  # should not raise


def test_log_event_truncates_long_ref():
    run_id = _rl_mod.open_run(purpose="test ref truncation")
    long_ref = "X" * 300
    _rl_mod.log_event("ref_test", ref=long_ref)
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ref FROM willow.run_events WHERE run_id = %s AND event_type = 'ref_test'",
            (run_id,),
        )
        row = cur.fetchone()
    conn.close()
    assert row is not None
    assert len(row[0]) <= 200
