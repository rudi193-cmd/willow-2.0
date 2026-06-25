"""Unit tests for WCE handoff-pair continuity metrics."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from willow.bench.continuity.handoff_eval import (
    evaluate_next_bite,
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
