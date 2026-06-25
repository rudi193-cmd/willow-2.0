"""Unit tests for WCE handoff-pair continuity metrics."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from willow.bench.continuity.handoff_eval import (
    boot_surfaced_items,
    evaluate_decision_persistence,
    evaluate_next_bite,
    evaluate_staleness_surfacing,
    evaluate_surfacing_precision,
    evaluate_thread_recall,
    signatures,
    texts_overlap,
)


def test_signatures_picks_pr_and_issue_tokens():
    sig = signatures("Merge PR #506 and fix codejail #309 quality gate")
    assert "#506" in sig or "pr#506" in sig or any("506" in s for s in sig)
    assert "#309" in sig


def test_thread_recall_matches_overlapping_pair():
    n = {
        "open_threads": [
            "Merge PR #506 — log-dampened ranking default",
            "AsyncAnthropic leak in locomo_llm.py",
        ],
    }
    n1 = {
        "understand": "We merged PR #506 with WCE and ranking fixes.",
        "summary": "",
        "what_was_done": ["Fixed AsyncAnthropic client leak in locomo_llm.py"],
        "open_threads": [],
    }
    result = evaluate_thread_recall(n, n1)
    assert result["recall"] == 1.0
    assert len(result["matched"]) == 2


def test_thread_recall_misses_unrelated_thread():
    n = {"open_threads": ["HomeGrid deferred migration"]}
    n1 = {
        "understand": "LoCoMo ranking and WCE harness shipped.",
        "summary": "",
        "what_was_done": [],
        "open_threads": [],
    }
    result = evaluate_thread_recall(n, n1)
    assert result["recall"] == 0.0


def test_next_bite_hit_when_n1_executes_bite():
    n = {"next_bite": "restart-server then run WCE ablation on log weight mode"}
    n1 = {
        "what_was_done": ["Restarted MCP server", "Ran WCE ablation for log weight mode"],
        "understand": "",
        "summary": "",
    }
    assert evaluate_next_bite(n, n1)["hit"] is True


def test_texts_overlap_requires_shared_signature():
    assert texts_overlap("detached Kart lane", "shipped detached lane via PR #503")
    assert not texts_overlap("unrelated topic entirely", "something else")


def test_boot_surfaced_items_caps_threads_and_atoms():
    n = {
        "open_threads": [f"thread-{i}" for i in range(8)],
        "surfaced_atom_ids": [f"{i:08X}" for i in range(5)],
    }
    items = boot_surfaced_items(n, max_threads=5, max_atoms=3)
    assert sum(1 for i in items if i["kind"] == "thread") == 5
    assert sum(1 for i in items if i["kind"] == "atom") == 3


def test_surfacing_precision_counts_used_boot_items():
    n = {
        "open_threads": ["Merge PR #507 WCE handoff tasks", "HomeGrid deferred"],
        "surfaced_atom_ids": ["DEADBEEF", "CAFEBABE"],
    }
    n1 = {
        "understand": "Merged PR #507 with handoff continuity metrics.",
        "summary": "",
        "what_was_done": [],
        "open_threads": [],
    }
    result = evaluate_surfacing_precision(n, n1, max_threads=5, max_atoms=3)
    assert result["n_surfaced"] == 4
    assert result["n_used"] >= 1
    assert result["precision"] is not None
    assert result["precision"] > 0


def test_decision_persistence_flags_reask_without_execution():
    n = {"agreements": ["Use detached Kart lane for long benchmark jobs"]}
    n1 = {
        "questions": ["Should we use detached Kart for benchmarks?", "What is the next single bite?"],
        "what_was_done": [],
        "understand": "",
        "summary": "",
    }
    result = evaluate_decision_persistence(n, n1)
    assert result["relitigation_rate"] == 1.0
    assert len(result["relitigated"]) == 1


def test_decision_persistence_passes_when_executed():
    n = {"agreements": ["Use detached Kart lane for long benchmark jobs"]}
    n1 = {
        "questions": ["What is the next single bite?"],
        "what_was_done": ["Shipped detached Kart lane for long benchmark jobs"],
        "understand": "",
        "summary": "",
    }
    result = evaluate_decision_persistence(n, n1)
    assert result["relitigation_rate"] == 0.0


def test_staleness_flags_when_corpus_marks_stale():
    n1 = {
        "understand": "Atom DEADBEEF is superseded — use the closure atom instead.",
        "summary": "",
        "what_was_done": [],
        "open_threads": [],
    }
    atoms = [{"id": "DEADBEEF", "title": "GAP1 still open", "summary": "fleet status metabolic"}]
    result = evaluate_staleness_surfacing(n1, atoms)
    assert result["n_mentioned"] == 1
    assert result["stale_flag_rate"] == 1.0
    assert result["acted_on_stale_rate"] == 0.0


def test_staleness_acted_on_without_flag():
    n1 = {
        "understand": "GAP1 is still open on fleet metabolic consecration.",
        "summary": "",
        "what_was_done": [],
        "open_threads": [],
    }
    atoms = [{"id": "DEADBEEF", "title": "GAP1 still open", "summary": "fleet status metabolic"}]
    result = evaluate_staleness_surfacing(n1, atoms)
    assert result["n_mentioned"] == 1
    assert result["stale_flag_rate"] == 0.0
    assert result["acted_on_stale_rate"] == 1.0
