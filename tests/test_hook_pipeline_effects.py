"""Hook-pipeline effect tests — batch 3 of the magma-layer audit.

The subsystem's prior tests verified shapes (isinstance, mock-was-called);
these verify effects: real KB rows land, regressions are not masked by
count math, quiet success is not logged as stalled, and the pipeline no
longer self-disables on an env var nobody sets.
"""
import types
import uuid

import pytest

from core.atom_extractor import Atom
from willow.hooks import runner
from willow.hooks.completion_hook import extract_test_atoms
from willow.hooks.kb_writer import write_atom_to_kb


def _report(**outcomes):
    return {"tests": [{"nodeid": k, "outcome": v} for k, v in outcomes.items()]}


# ── extract_test_atoms: set-diff semantics ───────────────────────────────────

def test_regression_not_masked_by_simultaneous_fix():
    """1 new pass + 1 new fail used to net to zero — the masking bug."""
    before = _report(**{"t::a": "passed", "t::b": "failed"})
    after = _report(**{"t::a": "failed", "t::b": "passed"})

    atoms = extract_test_atoms(before, after)
    titles = [a.title for a in atoms]

    assert any("REGRESSION" in t for t in titles), "regression masked"
    assert any("newly passing" in t for t in titles), "fix masked"
    regression = next(a for a in atoms if "REGRESSION" in a.title)
    assert regression.content["nodeids"] == ["t::a"]
    newly = next(a for a in atoms if "newly passing" in a.title)
    assert newly.content["nodeids"] == ["t::b"]


def test_newly_passing_lists_only_new_passes_not_all_passes():
    before = _report(**{"t::old": "passed", "t::fixme": "failed"})
    after = _report(**{"t::old": "passed", "t::fixme": "passed"})

    atoms = extract_test_atoms(before, after)
    newly = next(a for a in atoms if "newly passing" in a.title)
    assert newly.content["newly_passing"] == 1
    assert newly.content["nodeids"] == ["t::fixme"]
    assert "t::old" not in newly.summary


def test_removed_test_is_not_a_regression():
    before = _report(**{"t::gone": "passed", "t::stay": "passed"})
    after = _report(**{"t::stay": "passed"})

    atoms = extract_test_atoms(before, after)
    assert not any("REGRESSION" in a.title for a in atoms)


def test_no_before_results_yields_no_atoms():
    assert extract_test_atoms(None, _report(**{"t::a": "passed"})) == []


# ── runner: quiet success + env-gate default ─────────────────────────────────

@pytest.fixture()
def _pipeline_env(monkeypatch):
    logged = []
    monkeypatch.setattr(runner, "_log_execution", lambda *a, **kw: logged.append(kw) or True)
    monkeypatch.setattr(
        runner, "get_active_hooks",
        lambda category=None: [{"name": "quiet_hook", "handler_path": "x.py"}],
    )
    monkeypatch.setattr(
        runner, "run_hook_isolated",
        lambda *a, **kw: {"stdout": "", "stderr": "", "returncode": 0,
                          "elapsed_ms": 1, "timed_out": False},
    )
    monkeypatch.delenv("WILLOW_ATOM_EXTRACTION", raising=False)
    return logged


def test_quiet_success_is_ok_not_stalled(_pipeline_env):
    summary = runner.run_pipeline()
    assert summary["executed"] == 1
    assert summary["stalled"] == 0
    assert _pipeline_env[0]["status"] == "ok"
    assert _pipeline_env[0]["changed"] is False  # quiet, but healthy


def test_pipeline_sets_extraction_env_by_default(_pipeline_env):
    import os
    runner.run_pipeline()
    assert os.environ.get("WILLOW_ATOM_EXTRACTION") == "1", (
        "pipeline must be its own invocation point, not depend on external env"
    )


def test_pipeline_respects_explicit_disable(_pipeline_env, monkeypatch):
    import os
    monkeypatch.setenv("WILLOW_ATOM_EXTRACTION", "0")
    runner.run_pipeline()
    assert not os.environ.get("WILLOW_ATOM_EXTRACTION"), (
        "operator's explicit 0 must translate to disabled for child hooks"
    )


# ── conftest collection: real outcomes, real Session attrs ──────────────────

def test_logreport_collects_call_outcomes():
    import tests.conftest as c

    saved = dict(c._TEST_OUTCOMES)
    try:
        c._TEST_OUTCOMES.clear()
        c.pytest_runtest_logreport(
            types.SimpleNamespace(when="call", nodeid="t::x", outcome="passed"))
        c.pytest_runtest_logreport(
            types.SimpleNamespace(when="setup", nodeid="t::skip", outcome="skipped"))
        c.pytest_runtest_logreport(
            types.SimpleNamespace(when="setup", nodeid="t::x2", outcome="passed"))
        assert c._TEST_OUTCOMES == {"t::x": "passed", "t::skip": "skipped"}
    finally:
        c._TEST_OUTCOMES.clear()
        c._TEST_OUTCOMES.update(saved)


# ── end-to-end: atom actually lands in knowledge (real DB) ───────────────────

@pytest.fixture()
def pg_conn():
    from core.pg_bridge import PgBridge
    try:
        bridge = PgBridge()
    except Exception:
        pytest.skip("Postgres unavailable")
    yield bridge
    bridge.close()


def test_atom_lands_in_knowledge_and_dedups(pg_conn):
    tag = uuid.uuid4().hex[:10]
    atom = Atom(
        title=f"Tests: 2 newly passing [{tag}]",
        summary="effect-test atom",
        category="test",
        source_type="test_event",
        content={"newly_passing": 2, "nodeids": [f"t::{tag}"]},
    )

    assert write_atom_to_kb(atom, dedup_key=f"key-{tag}-1") is True

    cur = pg_conn.conn.cursor()
    cur.execute("SELECT id FROM knowledge WHERE content->>'dedup_key' = %s",
                (f"key-{tag}-1",))
    assert cur.fetchone() is not None, "atom did not land in knowledge"

    # Same dedup key → skipped, even with identical title.
    dup = Atom(
        title=atom.title, summary="dup", category="test",
        source_type="test_event", content={"nodeids": []},
    )
    assert write_atom_to_kb(dup, dedup_key=f"key-{tag}-1") is False

    # Same TITLE but different key → must be written (the old title-dedup
    # bug silently swallowed these forever).
    tomorrow = Atom(
        title=atom.title, summary="next day, same title", category="test",
        source_type="test_event", content={"nodeids": [f"t::{tag}b"]},
    )
    assert write_atom_to_kb(tomorrow, dedup_key=f"key-{tag}-2") is True, (
        "distinct event with recurring title was deduped away"
    )

    cur.execute("DELETE FROM knowledge WHERE content->>'dedup_key' LIKE %s",
                (f"key-{tag}-%",))
    pg_conn.conn.commit()
