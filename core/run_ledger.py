"""
core/run_ledger.py — Run Ledger v0.

Opens/closes runs in willow.runs and logs events to willow.run_events.
Reads/writes current run_id from /tmp/willow-run-{AGENT}.json so all
hooks in the same session share a single run_id without a DB query.
"""
import json
import os
from core.agent_identity import require_agent_name
import uuid
from datetime import datetime, timezone
from pathlib import Path

_AGENT = require_agent_name()
_DB = os.environ.get("WILLOW_PG_DB", "willow_19")
_USER = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))

_RUN_FILE = Path(f"/tmp/willow-run-{_AGENT}.json")
_MAX_REF_LEN = 200


def _connect():
    import psycopg2
    return psycopg2.connect(dbname=_DB, user=_USER)


def open_run(
    purpose: str = "",
    repo_roots: list[str] | None = None,
    parent_run_id: str | None = None,
    *,
    write_tmp: bool = True,
) -> str:
    """Create a run record. When ``write_tmp`` is True (default), persist current run_id to
    ``/tmp/willow-run-{AGENT}.json`` for hooks in the same OS process.

    Callers that open a **nested** run (e.g. Kart child) must pass ``write_tmp=False`` so they
    do not clobber the parent session's tmp pointer; they must close via explicit ``run_id``.
    Returns '' on DB failure — never a phantom UUID.
    """
    run_id = str(uuid.uuid4())
    try:
        conn = _connect()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO willow.runs (id, parent_run_id, purpose, initiator, repo_roots, status)
            VALUES (%s, %s, %s, %s, %s, 'running')
            """,
            (run_id, parent_run_id, purpose[:200] if purpose else None,
             _AGENT, repo_roots or []),
        )
        cur.execute(
            "INSERT INTO willow.run_agents (run_id, agent) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (run_id, _AGENT),
        )
        conn.close()
        if write_tmp:
            _write_run_file(run_id)
    except Exception as e:
        _err(f"open_run: {e}")
        return ""
    return run_id


def close_run(status: str = "completed") -> None:
    """Mark the current run as completed/abandoned/crashed."""
    run_id = current_run_id()
    if not run_id:
        return
    try:
        conn = _connect()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "UPDATE willow.runs SET status=%s, ended_at=now() WHERE id=%s AND status='running'",
            (status, run_id),
        )
        conn.close()
    except Exception as e:
        _err(f"close_run: {e}")
    finally:
        _clear_run_file()


def log_event(event_type: str, ref: str = "", run_id: str | None = None) -> None:
    """Append one event row to willow.run_events. Best-effort — never raises."""
    rid = run_id or current_run_id()
    if not rid:
        return
    try:
        conn = _connect()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO willow.run_events (run_id, agent, event_type, ref) VALUES (%s, %s, %s, %s)",
            (rid, _AGENT, event_type, (ref or "")[:_MAX_REF_LEN]),
        )
        conn.close()
    except Exception as e:
        _err(f"log_event: {e}")


def join_run(run_id: str) -> None:
    """Register this agent as a contributor to an existing run."""
    try:
        conn = _connect()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO willow.run_agents (run_id, agent) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (run_id, _AGENT),
        )
        conn.close()
        _write_run_file(run_id)
    except Exception as e:
        _err(f"join_run: {e}")


def current_run_id() -> str | None:
    """Read run_id from the session-local tmp file. Returns None if not set."""
    try:
        data = json.loads(_RUN_FILE.read_text())
        return data.get("run_id")
    except Exception:
        return None


def _write_run_file(run_id: str) -> None:
    try:
        _RUN_FILE.write_text(json.dumps({
            "run_id": run_id,
            "agent": _AGENT,
            "written_at": datetime.now(timezone.utc).isoformat(),
        }))
    except Exception:
        pass


def _clear_run_file() -> None:
    try:
        _RUN_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _err(msg: str) -> None:
    try:
        log = Path.home() / ".willow" / "logs" / "run_ledger_errors.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")
    except Exception:
        pass
