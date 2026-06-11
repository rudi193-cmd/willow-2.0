import scripts.session_close as session_close


GOOD = """---
agent: tester
date: 2026-06-10
session: 2026-06-10a
runtime: claude-code
format: v2
---

# HANDOFF: test

## What I Now Understand

Things.

## Open Threads

- **one** — open item.

## What We Agreed On

- a decision

## 17 Questions

Q1: open?
Q17: the next bite
"""


def _write(tmp_path, agent, text):
    d = tmp_path / "handoffs" / agent
    d.mkdir(parents=True, exist_ok=True)
    (d / "session_handoff-2026-06-10_tester.md").write_text(text, encoding="utf-8")


def _gate(tmp_path, monkeypatch, agent="tester"):
    monkeypatch.setattr(session_close, "willow_home", lambda _repo: tmp_path)
    return session_close.check_handoff_completeness(agent)


def test_complete_handoff_passes(tmp_path, monkeypatch):
    _write(tmp_path, "tester", GOOD)
    ok, problems = _gate(tmp_path, monkeypatch)
    assert ok, problems


def test_missing_q17_rejected(tmp_path, monkeypatch):
    _write(tmp_path, "tester", GOOD.replace("Q17: the next bite\n", ""))
    ok, problems = _gate(tmp_path, monkeypatch)
    assert not ok
    assert any("Q17" in p for p in problems)


def test_empty_open_threads_rejected(tmp_path, monkeypatch):
    _write(tmp_path, "tester", GOOD.replace("- **one** — open item.\n", ""))
    ok, problems = _gate(tmp_path, monkeypatch)
    assert not ok
    assert any("Open Threads" in p for p in problems)


def test_missing_v2_rejected(tmp_path, monkeypatch):
    _write(tmp_path, "tester", GOOD.replace("format: v2\n", ""))
    ok, problems = _gate(tmp_path, monkeypatch)
    assert not ok
    assert any("format: v2" in p for p in problems)


def test_no_handoffs_rejected(tmp_path, monkeypatch):
    ok, problems = _gate(tmp_path, monkeypatch, agent="ghost")
    assert not ok
