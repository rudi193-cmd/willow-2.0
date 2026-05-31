"""Tests for sandbox git-shaped engine (WLGSM reference). b17: GSSM6 · ΔΣ=42"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sandbox.engine import GitShapedError, advance, preview_advance
from sandbox.gate_form import NewFeatureGate
from sandbox.model import ShapeState, create_issue
from sandbox.reporting import markdown_table
from sandbox.store import JsonStore


def test_happy_path_linear() -> None:
    c = create_issue("wire foo", subject="svc/foo", flag_id="")
    assert c.state == ShapeState.issue
    assert c.created_at and c.updated_at
    advance(c, ShapeState.draft, actor="hanuman", note="worktree")
    advance(c, ShapeState.open, actor="hanuman", note="grove+kb seed")
    advance(c, ShapeState.checks, actor="kart", note="pytest green")
    advance(c, ShapeState.review, actor="sean", note="lgtm pending")
    advance(c, ShapeState.merged, actor="sean", note="ratified")
    advance(c, ShapeState.archived, actor="hanuman", note="superseded by v2")
    assert c.state == ShapeState.archived
    assert len(c.history) == 6
    assert c.updated_at == c.history[-1].at


def test_checks_fail_returns_to_open() -> None:
    c = create_issue("flaky")
    advance(c, ShapeState.draft, actor="a")
    advance(c, ShapeState.open, actor="a")
    advance(c, ShapeState.checks, actor="ci")
    advance(c, ShapeState.open, actor="ci", note="fix tests")
    assert c.state == ShapeState.open


def test_illegal_skip_to_merge() -> None:
    c = create_issue("skip review")
    advance(c, ShapeState.draft, actor="a")
    with pytest.raises(GitShapedError):
        advance(c, ShapeState.merged, actor="a")


def test_gate_requires_all_fields() -> None:
    g = NewFeatureGate(
        state_touch="3",
        open_pr_equivalent="",
        merge_equivalent="x",
        archive_equivalent="y",
    )
    assert not g.ok()
    assert "open_pr_equivalent" in " ".join(g.validate())


def test_gate_ok() -> None:
    g = NewFeatureGate(
        state_touch="3",
        open_pr_equivalent="Grove #architecture + KB seed",
        merge_equivalent="ingest + ledger",
        archive_equivalent="domain=archived",
    )
    assert g.ok()


def test_json_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    st = JsonStore(p)
    c = create_issue("rt")
    advance(c, ShapeState.draft, actor="t")
    st.upsert(c)
    st2 = JsonStore(p)
    got = st2.get(c.id)
    assert got is not None
    assert got.state == ShapeState.draft
    assert got.created_at
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert len(raw) == 1


def test_preview_does_not_mutate_original() -> None:
    c = create_issue("p")
    advance(c, ShapeState.draft, actor="x")
    copy.deepcopy(c)
    pv = preview_advance(c, ShapeState.open, actor="y", note="peek")
    assert c.state == ShapeState.draft
    assert len(c.history) == 1
    assert pv.state == ShapeState.open
    assert len(pv.history) == 2


def test_delete_and_clear(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    st = JsonStore(p)
    a = create_issue("a")
    b = create_issue("b")
    st.upsert(a)
    st.upsert(b)
    assert st.delete(a.id) is True
    assert st.get(a.id) is None
    assert st.get(b.id) is not None
    st.clear()
    assert st.load_all() == []


def test_markdown_report_empty() -> None:
    assert "empty" in markdown_table([]).lower() or "—" in markdown_table([])


def test_markdown_report_row(tmp_path: Path) -> None:
    st = JsonStore(tmp_path / "m.json")
    c = create_issue("titled")
    st.upsert(c)
    md = markdown_table(st.load_all())
    assert "titled" in md
    assert c.id in md
