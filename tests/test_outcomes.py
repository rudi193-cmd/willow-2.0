"""
Integration tests for the Outcomes API wiring in Willow.
Tests PgBridge outcome methods and kart_poll phase routing.
Does NOT call the Anthropic Outcomes API — mocked at core.outcomes.run_outcome.
Requires live Postgres (willow_20_test).
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

# CI Postgres migrations can exceed the default 60s pytest-timeout.
pytestmark = pytest.mark.timeout(180)


@pytest.fixture(scope="module")
def pg():
    b = PgBridge()
    run_migrations(b.conn)
    yield b
    b.close()


# ── PgBridge outcome methods ──────────────────────────────────────────────────

def test_outcome_agent_register_and_get(pg):
    rec = pg.outcome_agent_register(
        name="test-agent",
        agent_id="agt_test123",
        environment_id="env_test456",
        description="unit test agent",
        created_by="test",
    )
    assert rec["name"] == "test-agent"
    assert rec["agent_id"] == "agt_test123"
    assert rec["id"] is not None  # returns full row now

    fetched = pg.outcome_agent_get("test-agent")
    assert fetched is not None
    assert fetched["environment_id"] == "env_test456"


def test_outcome_agent_upserts(pg):
    pg.outcome_agent_register("test-agent-v2", "agt_v1", "env_v1", "v1", "test")
    pg.outcome_agent_register("test-agent-v2", "agt_v2", "env_v2", "v2", "test")
    fetched = pg.outcome_agent_get("test-agent-v2")
    assert fetched["agent_id"] == "agt_v2"


def test_outcome_run_lifecycle(pg):
    agent = pg.outcome_agent_register("test-runner", "agt_r", "env_r", "", "test")

    run_id = pg.outcome_run_create(agent["id"], "Summarize the KB",
                                    "Output must contain a summary.", 3, "test")
    assert run_id

    row = pg.outcome_run_get(run_id)
    assert row is not None
    assert row["status"] == "pending"
    assert row["outcome_agent_id"] == agent["id"]

    pg.outcome_run_update(run_id, status="satisfied", explanation="Looks good",
                           session_id="sess_abc123")
    row = pg.outcome_run_get(run_id)
    assert row["status"] == "satisfied"
    assert row["session_id"] == "sess_abc123"
    assert row["explanation"] == "Looks good"


# ── kart_poll rubric routing ──────────────────────────────────────────────────

def test_workflow_phase_routes_to_outcomes_when_rubric_present(pg):
    """A workflow phase with rubric + outcome_agent should call run_outcome, not _call_llm."""
    pg.outcome_agent_register("phase-agent", "agt_phase", "env_phase", "", "test")
    assert pg.outcome_agent_get("phase-agent") is not None

    wf = pg.workflow_define(
        name="test_outcomes_wf",
        definition={
            "phases": {
                "grade": {
                    "prompt":        "Grade this: {{input.text}}",
                    "depends_on":    [],
                    "rubric":        "Output must be a grade A-F.",
                    "outcome_agent": "phase-agent",
                }
            }
        },
        created_by="test",
    )

    run_id = pg.workflow_run_create(wf["id"], {"text": "Willow is great"}, "test")

    phase_input = {
        "prompt":      "Grade this: Willow is great",
        "phase_name":  "grade",
        "rubric":      "Output must be a grade A-F.",
        "outcome_agent": "phase-agent",
    }
    payload_dict = {
        "type":       "workflow_phase",
        "run_id":     run_id,
        "phase_name": "grade",
        "phase_input": phase_input,
    }
    task_id = pg.submit_task(json.dumps(payload_dict), submitted_by="test", agent="kart")
    pg.workflow_phase_create(run_id, "grade", phase_input, task_id)
    pg.workflow_run_update(run_id, "running")

    from core import kart_execute

    mock_outcome = {
        "result":      "satisfied",
        "explanation": "Grade A given",
        "success":     True,
        "iterations":  1,
        "session_id":  "sess_mock",
    }

    with unittest.mock.patch("core.outcomes.run_outcome", return_value=mock_outcome) as m_outcome, \
         unittest.mock.patch.object(kart_execute, "_call_llm") as m_llm:
        status, result = kart_execute.run_workflow_phase(pg, task_id, payload_dict)

    assert status == "completed"
    m_outcome.assert_called_once()
    m_llm.assert_not_called()

    phases = pg.workflow_phases_for_run(run_id)
    grade_phase = next(p for p in phases if p["phase_name"] == "grade")
    assert grade_phase["status"] == "completed"
    assert grade_phase["output"]["result"] == "satisfied"


def test_workflow_phase_uses_llm_without_rubric(pg):
    """A phase without rubric should still use _call_llm."""
    wf = pg.workflow_define(
        name="test_no_rubric_wf",
        definition={
            "phases": {
                "extract": {
                    "prompt":     "Extract: {{input.text}}",
                    "depends_on": [],
                    "output_schema": {"facts": ["string"]},
                }
            }
        },
        created_by="test",
    )

    run_id = pg.workflow_run_create(wf["id"], {"text": "hello"}, "test")
    phase_input = {
        "prompt":        "Extract: hello",
        "phase_name":    "extract",
        "output_schema": {"facts": ["string"]},
    }
    payload_dict = {
        "type":       "workflow_phase",
        "run_id":     run_id,
        "phase_name": "extract",
        "phase_input": phase_input,
    }
    task_id = pg.submit_task(json.dumps(payload_dict), submitted_by="test", agent="kart")
    pg.workflow_phase_create(run_id, "extract", phase_input, task_id)
    pg.workflow_run_update(run_id, "running")

    from core import kart_execute

    mock_llm_output = {"facts": ["hello is a greeting"], "_elapsed_s": 0.1}

    with unittest.mock.patch.object(kart_execute, "_call_llm", return_value=mock_llm_output) as m_llm, \
         unittest.mock.patch("core.outcomes.run_outcome") as m_outcome:
        status, result = kart_execute.run_workflow_phase(pg, task_id, payload_dict)

    assert status == "completed"
    m_llm.assert_called_once()
    m_outcome.assert_not_called()
