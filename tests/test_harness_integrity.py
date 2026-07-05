"""Harness integrity + runner check-predicate tests (no model calls).

Two effect layers:
- every harness directory is complete, parseable, and internally consistent
  (fewshot outputs satisfy their own schema's required/enum constraints);
- the runner's check predicates behave — they are the verifier, so they get
  their own tests.
"""
from pathlib import Path

import pytest

from willow.fylgja.harnesses import runner

HARNESS_ROOT = Path(__file__).parent.parent / "willow" / "fylgja" / "harnesses"
HARNESS_DIRS = sorted(
    d for d in HARNESS_ROOT.iterdir()
    if d.is_dir() and (d / "harness.json").exists()
)

REQUIRED_FILES = ["harness.json", "prompt.md", "schema.json", "fewshot.json", "fixtures.jsonl"]
VERIFY_CLASSES = {"recount", "exitcode", "schema", "coverage", "containment"}


def test_harnesses_discovered():
    names = {d.name for d in HARNESS_DIRS}
    assert {"commit_atom", "dream_synthesis", "briefing_draft"} <= names


@pytest.mark.parametrize("harness_dir", HARNESS_DIRS, ids=lambda d: d.name)
def test_harness_dir_complete(harness_dir):
    for fname in REQUIRED_FILES:
        assert (harness_dir / fname).exists(), f"{harness_dir.name} missing {fname}"
    assert (harness_dir / "failure_modes.md").exists()


@pytest.mark.parametrize("harness_dir", HARNESS_DIRS, ids=lambda d: d.name)
def test_harness_loads_and_declares_verify_class(harness_dir):
    harness = runner.load_harness(harness_dir)
    assert harness["meta"]["verify_class"] in VERIFY_CLASSES
    assert harness["meta"]["model"]
    assert harness["fixtures"], "a harness without fixtures cannot be evaluated"
    for fixture in harness["fixtures"]:
        assert fixture.get("checks"), "every fixture must carry checks"
        for check in fixture["checks"]:
            assert check["kind"] in runner.CHECKS, f"unknown check {check['kind']}"


def _validate_against_schema(obj, schema):
    """Minimal structural validation: required, enum, maxLength, additionalProperties."""
    assert isinstance(obj, dict)
    props = schema.get("properties", {})
    for key in schema.get("required", []):
        assert key in obj, f"missing required {key}"
    if schema.get("additionalProperties") is False:
        assert set(obj) <= set(props), f"extra keys: {set(obj) - set(props)}"
    for key, spec in props.items():
        if key not in obj:
            continue
        val = obj[key]
        if "enum" in spec:
            assert val in spec["enum"], f"{key}={val!r} not in enum"
        if spec.get("type") == "string" and "maxLength" in spec:
            assert len(val) <= spec["maxLength"], f"{key} exceeds maxLength"
        if spec.get("type") == "array" and "items" in spec and isinstance(val, list):
            item_spec = spec["items"]
            if item_spec.get("type") == "object":
                for item in val:
                    _validate_against_schema(item, item_spec)


@pytest.mark.parametrize("harness_dir", HARNESS_DIRS, ids=lambda d: d.name)
def test_fewshot_outputs_satisfy_own_schema(harness_dir):
    harness = runner.load_harness(harness_dir)
    for shot in harness["fewshot"]:
        _validate_against_schema(shot["output"], harness["schema"])


# ── Runner check predicates ──────────────────────────────────────────────────

def test_grounded_rejects_invented_values():
    out = {"files_touched": ["core/a.py", "core/invented.py"]}
    assert runner.check_grounded(out, {"path": "files_touched"}, "diff: core/a.py") is False
    out = {"files_touched": ["core/a.py"]}
    assert runner.check_grounded(out, {"path": "files_touched"}, "diff: core/a.py") is True


def test_get_path_traverses_lists():
    obj = {"insights": [{"evidence_atom_ids": ["A1", "A2"]}]}
    assert runner._get_path(obj, "insights.0.evidence_atom_ids") == ["A1", "A2"]
    assert runner._get_path(obj, "insights.3.evidence_atom_ids") is None


def test_contains_and_not_contains():
    out = {"title": "pg_bridge: destructor fix"}
    assert runner.check_contains(out, {"path": "title", "any": ["destructor"]}, "") is True
    assert runner.check_contains(out, {"path": "title", "any": ["banana"]}, "") is False
    assert runner.check_not_contains(out, {"values": ["banana"]}, "") is True
    assert runner.check_not_contains(out, {"values": ["destructor"]}, "") is False


def test_containment_harness_can_never_pass(monkeypatch):
    """The runner, not the prompt, enforces review-queue authority."""
    harness = {
        "meta": {"name": "t", "verify_class": "containment"},
        "prompt": "p",
        "schema": {},
        "fewshot": [],
    }
    monkeypatch.setattr(runner, "call_ollama", lambda *a, **k: {"ok": True})
    verdict, failures = runner.run_fixture(harness, {"input": "x", "checks": []}, "m", {})
    assert verdict == runner.CONTAINED
    assert failures == []


def test_coverage_harness_passes_when_checks_hold(monkeypatch):
    harness = {
        "meta": {"name": "t", "verify_class": "coverage"},
        "prompt": "p",
        "schema": {},
        "fewshot": [],
    }
    monkeypatch.setattr(runner, "call_ollama", lambda *a, **k: {"title": "soil fix"})
    fixture = {"input": "x", "checks": [{"kind": "contains", "path": "title", "any": ["soil"]}]}
    verdict, _ = runner.run_fixture(harness, fixture, "m", {})
    assert verdict == runner.PASS

    fixture = {"input": "x", "checks": [{"kind": "contains", "path": "title", "any": ["kart"]}]}
    verdict, failures = runner.run_fixture(harness, fixture, "m", {})
    assert verdict == runner.FAIL
    assert failures
