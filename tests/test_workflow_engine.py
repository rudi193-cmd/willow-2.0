"""
Integration tests for the Willow workflow engine.
Tests the DAG executor end-to-end: define → run → phase execution → status.
Requires live Postgres (willow_20_test). Does NOT call the Anthropic API —
LLM calls are mocked at the kart_poll layer.
"""
import json
import os
import sys
import unittest.mock
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("WILLOW_PG_DB", "willow_20_test")

from core.pg_bridge import PgBridge, run_migrations


@pytest.fixture(scope="module")
def pg():
    b = PgBridge()
    run_migrations(b.conn)
    yield b
    b.close()


# ── Workflow definition ───────────────────────────────────────────────────────

def test_workflow_define_and_get(pg):
    result = pg.workflow_define(
        name="test_simple",
        definition={
            "phases": {
                "extract": {
                    "prompt": "Extract facts from: {{input.text}}",
                    "depends_on": [],
                    "output_schema": {"facts": ["string"]},
                    "model": "claude-haiku-4-5-20251001",
                },
                "summarize": {
                    "prompt": "Summarize these facts: {{phases.extract.facts}}",
                    "depends_on": ["extract"],
                    "output_schema": {"summary": "string"},
                },
            }
        },
        created_by="test",
    )
    assert result.get("name") == "test_simple"

    wf = pg.workflow_get("test_simple")
    assert wf is not None
    assert "phases" in wf["definition"]
    assert "extract" in wf["definition"]["phases"]
    assert "summarize" in wf["definition"]["phases"]


def test_workflow_define_upserts_version(pg):
    initial = (pg.workflow_get("test_versioned") or {}).get("version", 0)
    pg.workflow_define("test_versioned", {"phases": {"a": {"prompt": "v1", "depends_on": []}}})
    pg.workflow_define("test_versioned", {"phases": {"a": {"prompt": "v2", "depends_on": []}}})
    wf = pg.workflow_get("test_versioned")
    assert wf["version"] == initial + 2
    assert wf["definition"]["phases"]["a"]["prompt"] == "v2"


def test_workflow_list(pg):
    rows = pg.workflow_list()
    assert isinstance(rows, list)
    assert any(r["name"] == "test_simple" for r in rows)


# ── Run creation + phase queuing ──────────────────────────────────────────────

def test_workflow_run_create(pg):
    wf = pg.workflow_get("test_simple")
    run_id = pg.workflow_run_create(wf["id"], {"text": "Hello world"}, created_by="test")
    assert run_id is not None

    run = pg.workflow_run_get(run_id)
    assert run["status"] == "pending"
    assert run["input"]["text"] == "Hello world"


def test_workflow_phase_create(pg):
    wf    = pg.workflow_get("test_simple")
    run_id = pg.workflow_run_create(wf["id"], {"text": "test"}, created_by="test")
    task_id = pg.submit_task("echo test", submitted_by="test", agent="kart")

    ph_id = pg.workflow_phase_create(run_id, "extract", {"prompt": "Extract: test"}, task_id)
    assert ph_id is not None

    phases = pg.workflow_phases_for_run(run_id)
    assert any(p["phase_name"] == "extract" for p in phases)


# ── Phase executor (mocked LLM) ───────────────────────────────────────────────

def test_workflow_phase_executor_full_dag(pg):
    """Run a 2-phase DAG: extract → summarize. Mock the LLM call."""
    wf = pg.workflow_get("test_simple")
    run_id = pg.workflow_run_create(wf["id"], {"text": "Willow is a local-first AI stack"}, "test")

    # Simulate what workflow_run MCP tool does: queue first phase
    phases     = wf["definition"]["phases"]
    phase_name = "extract"
    phase_def  = phases[phase_name]
    phase_input = {
        "prompt":        "Extract facts from: Willow is a local-first AI stack",
        "model":         "claude-haiku-4-5-20251001",
        "output_schema": phase_def["output_schema"],
        "phase_name":    phase_name,
    }
    payload = json.dumps({
        "type":        "workflow_phase",
        "run_id":      run_id,
        "phase_name":  phase_name,
        "phase_input": phase_input,
    })
    task_id = pg.submit_task(payload, submitted_by="test", agent="kart")
    pg.workflow_phase_create(run_id, phase_name, phase_input, task_id)
    pg.workflow_run_update(run_id, "running")

    # Mock LLM and run the phase executor
    from scripts import kart_poll
    mock_output = {"facts": ["Willow is local-first", "Willow is an AI stack"], "_elapsed_s": 0.1}

    with unittest.mock.patch.object(kart_poll, "_call_llm", return_value=mock_output):
        status, result = kart_poll._run_workflow_phase(pg, task_id, json.loads(payload))

    assert status == "completed"
    assert result["phase"] == "extract"

    # Verify output stored in DB
    phases_db = pg.workflow_phases_for_run(run_id)
    extract_phase = next(p for p in phases_db if p["phase_name"] == "extract")
    assert extract_phase["status"] == "completed"
    assert extract_phase["output"]["facts"] == mock_output["facts"]

    # Verify summarize phase was auto-queued
    assert any(p["phase_name"] == "summarize" for p in phases_db), \
        "summarize phase should have been queued after extract completed"


# ── Cancel ────────────────────────────────────────────────────────────────────

def test_workflow_cancel(pg):
    wf     = pg.workflow_get("test_simple")
    run_id = pg.workflow_run_create(wf["id"], {}, "test")
    pg.workflow_run_update(run_id, "running")

    result = pg.workflow_cancel(run_id)
    assert result["cancelled"] is True

    run = pg.workflow_run_get(run_id)
    assert run["status"] == "cancelled"


# ── Status ────────────────────────────────────────────────────────────────────

def test_workflow_status_shape(pg):
    wf     = pg.workflow_get("test_simple")
    run_id = pg.workflow_run_create(wf["id"], {"text": "status test"}, "test")
    task_id = pg.submit_task("echo x", submitted_by="test", agent="kart")
    pg.workflow_phase_create(run_id, "extract", {}, task_id)

    status = pg.workflow_status(run_id)
    assert "run" in status
    assert "phases" in status
    assert "extract" in status["phases"]
    assert status["total"] >= 1
