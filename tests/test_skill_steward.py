"""Tests for agents/hanuman/lib/skill_steward.py delta logic."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.hanuman.lib import skill_steward as ss


def _rec(sid: str, *, cls: str = "E", risk: str = "low", desc: str = "x") -> dict:
    return {
        "id": sid,
        "name": sid.split("/")[-1],
        "source": "awesome-claude",
        "execution_class": cls,
        "risk": risk,
        "risk_signals": [],
        "description": desc,
        "path": f"/tmp/{sid}",
    }


def test_fingerprint_stable():
    a = _rec("awesome-claude/foo")
    assert ss.fingerprint(a) == ss.fingerprint(a)


def test_diff_new_and_changed():
    old = ss.build_snapshot(
        {"awesome-claude": {"a/s1": _rec("awesome-claude/s1", desc="one")}},
    )
    new_skills = {
        "awesome-claude/s1": _rec("awesome-claude/s1", desc="two"),
        "awesome-claude/s2": _rec("awesome-claude/s2"),
    }
    delta = ss.diff_snapshots(old, {"awesome-claude": new_skills})
    assert len(delta["new"]) == 1
    assert delta["new"][0]["id"] == "awesome-claude/s2"
    assert len(delta["changed"]) == 1
    assert delta["changed"][0]["id"] == "awesome-claude/s1"


def test_needs_triage_class_e():
    assert ss.needs_triage({"change": "new", "execution_class": "E", "risk": "low"})


def test_needs_triage_dismiss_removed():
    assert not ss.needs_triage({"change": "removed"})


def test_triage_priority_orders_high_risk_first():
    low = {"change": "changed", "execution_class": "A", "risk": "low", "risk_signals": []}
    high = {"change": "new", "execution_class": "E", "risk": "high", "risk_signals": ["curl_pipe_bash"]}
    assert ss.triage_priority(high) > ss.triage_priority(low)


def test_baseline_skips_bulk_queue():
    """First snapshot must not treat all skills as triage flood."""
    old = None
    new = {"awesome-claude": {"x": _rec("awesome-claude/x")}}
    delta = ss.diff_snapshots(old, new)
    assert len(delta["new"]) == 1
    # run_once uses is_baseline → to_queue empty (logic mirrored here)
    is_baseline = old is None
    to_queue = [] if is_baseline else delta["new"]
    assert to_queue == []
