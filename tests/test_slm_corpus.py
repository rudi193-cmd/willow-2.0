"""Tests for tools/slm_corpus — template fidelity and contract validation.

Shape-only tests are banned here (the magma-layer rule): each test asserts
the actual produced strings/verdicts, not just types.
"""
from __future__ import annotations

import json

import pytest

from tools.slm_corpus import templates as T
from tools.slm_corpus.harvest import redact


# ── template fidelity: messages must match production construction ───────────

def test_orin_summarize_matches_production():
    msgs = T.build_messages("orin_summarize", {"content": "some text"})
    assert msgs[0]["role"] == "system"
    assert '"bullets"' in msgs[0]["content"] and '"one_line"' in msgs[0]["content"]
    assert msgs[1]["content"] == (
        "Summarize the following into 3-5 key bullet points:\n\nsome text"
    )


def test_orin_classify_lists_categories_and_obligations():
    msgs = T.build_messages(
        "orin_classify",
        {"content": "x", "categories": ["a", "b"], "context": "ctx"},
    )
    assert '"a", "b"' in msgs[0]["content"]
    assert '"task", "decision", "reference", "fyi", "none"' in msgs[0]["content"]
    assert msgs[1]["content"].startswith("Context:\nctx\n\n")


def test_intake_route_uses_production_context_and_budget():
    msgs = T.build_messages("intake_route", {"content": "z" * 2000})
    assert "routing a knowledge record" in msgs[1]["content"]
    # content truncated to 800 chars inside the user message
    assert "z" * 800 in msgs[1]["content"]
    assert "z" * 801 not in msgs[1]["content"]


def test_orin_extract_truncates_to_budget():
    msgs = T.build_messages("orin_extract", {"content": "y" * 10_000})
    assert "y" * T.EXTRACT_CONTENT_BUDGET in msgs[1]["content"]
    assert "y" * (T.EXTRACT_CONTENT_BUDGET + 1) not in msgs[1]["content"]


def test_dream_tension_truncates_summaries_to_200():
    msgs = T.build_messages("dream_tension", {
        "title_a": "A", "summary_a": "s" * 500,
        "title_b": "B", "summary_b": "t" * 500,
    })
    assert "s" * 200 in msgs[1]["content"]
    assert "s" * 201 not in msgs[1]["content"]
    assert msgs[1]["content"].rstrip().endswith(
        "Reply TENSION or COMPATIBLE (one word), then one sentence.")


def test_drift_verdict_prompt_has_format_block():
    msgs = T.build_messages("drift_verdict", {
        "title": "t", "summary": "s", "file_path": "core/x.py",
        "file_content": "def f(): pass",
    })
    assert "VERDICT: <current|drifted|uncertain>" in msgs[1]["content"]
    assert "CURRENT CODE (core/x.py):" in msgs[1]["content"]


def test_unknown_task_type_raises():
    with pytest.raises(ValueError):
        T.build_messages("nope", {})


# ── validators: accept the contract, reject drift ─────────────────────────────

def test_validate_summarize_accepts_and_rejects():
    ok, _ = T.validate_output(
        "orin_summarize", {},
        '{"bullets": ["a", "b", "c"], "one_line": "short"}')
    assert ok
    for bad in (
        '{"bullets": [], "one_line": "x"}',          # empty bullets
        '{"bullets": ["1","2","3","4","5","6"], "one_line": "x"}',  # >5
        '{"one_line": "x"}',                          # missing bullets
        "not json at all",
    ):
        ok, reason = T.validate_output("orin_summarize", {}, bad)
        assert not ok, bad
        assert reason


def test_validate_classify_checks_category_membership():
    payload = {"categories": ["red", "blue"]}
    good = '{"category": "red", "confidence": 0.9, "reason": "r", "obligation": "none"}'
    assert T.validate_output("orin_classify", payload, good)[0]
    wrong_cat = good.replace("red", "green")
    assert not T.validate_output("orin_classify", payload, wrong_cat)[0]
    out_of_range = good.replace("0.9", "1.7")
    assert not T.validate_output("orin_classify", payload, out_of_range)[0]


def test_validate_extract_enforces_atom_shape():
    good = json.dumps([{"title": "t", "summary": "s", "category": "code"}])
    assert T.validate_output("orin_extract", {}, good)[0]
    bad_cat = json.dumps([{"title": "t", "summary": "s", "category": "banana"}])
    assert not T.validate_output("orin_extract", {}, bad_cat)[0]
    assert not T.validate_output("orin_extract", {}, "[]")[0]


def test_validate_tension_requires_boolean_conflict():
    good = '{"conflict": true, "score": 0.8, "reason": "contradicts"}'
    assert T.validate_output("orin_tension", {}, good)[0]
    stringy = '{"conflict": "true", "score": 0.8, "reason": "r"}'
    assert not T.validate_output("orin_tension", {}, stringy)[0]


def test_validate_dream_tension_first_word():
    assert T.validate_output(
        "dream_tension", {}, "TENSION — these two claims disagree on the default model.")[0]
    assert T.validate_output(
        "dream_tension", {}, "COMPATIBLE. Both describe different subsystems.")[0]
    assert not T.validate_output("dream_tension", {}, "Maybe? Hard to say.")[0]
    assert not T.validate_output("dream_tension", {}, "TENSION")[0]  # no sentence


def test_validate_drift_verdict_lines():
    good = "VERDICT: drifted\nEVIDENCE: the function was renamed and the flag removed."
    assert T.validate_output("drift_verdict", {}, good)[0]
    assert not T.validate_output("drift_verdict", {}, "VERDICT: drifted\nEVIDENCE: no.")[0]
    assert not T.validate_output("drift_verdict", {}, "drifted, because reasons")[0]


def test_canonicalize_strips_fences():
    fenced = '```json\n{"conflict": false, "score": 0.1, "reason": "r"}\n```'
    out = T.canonicalize_output("orin_tension", fenced)
    assert out == '{"conflict": false, "score": 0.1, "reason": "r"}'
    assert T.canonicalize_output("dream_synthesis", "  text  ") == "text"


# ── redaction ─────────────────────────────────────────────────────────────────

def test_redact_common_secret_shapes():
    s = ("token ghp_abcdefghijklmnopqrstuvwxyz123456 and "
         "sk-proj-abcdefghijklmnopqrstuvwx and AKIAIOSFODNN7EXAMPLE and "
         "api_key=supersecretvalue123")
    r = redact(s)
    assert "ghp_" not in r
    assert "sk-proj" not in r
    assert "AKIA" not in r
    assert "supersecretvalue123" not in r
    assert r.count("[REDACTED]") >= 4


def test_redact_leaves_normal_text_alone():
    s = "PgBridge.__del__ self-deadlocked psycopg2's pool lock during GC"
    assert redact(s) == s
