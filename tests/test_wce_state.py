"""Unit tests for weekly WCE scheduling helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.wce_state import extract_wce_metrics, format_wce_summary_line, wce_conditions


class _FakeStore:
    def __init__(self, state: dict | None = None):
        self._state = state or {}

    def get(self, collection: str, record_id: str):
        if collection.endswith("/wce") and record_id == "state":
            return self._state
        return None


def test_wce_conditions_due_when_never_run():
    check = wce_conditions("willow", _FakeStore())
    assert check["should_run"] is True


def test_wce_conditions_skips_when_recent():
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    check = wce_conditions("willow", _FakeStore({"last_run_at": recent}))
    assert check["should_run"] is False


def test_extract_wce_metrics_builds_vector():
    payload = {
        "timestamp": "20260625T120000Z",
        "handoff": {
            "summary": {
                "thread_recall_mean": 0.63,
                "next_bite_hit_rate": 0.43,
                "surfacing_precision_mean": 0.35,
                "relitigation_rate_mean": 0.31,
            }
        },
        "cold_recall": {
            "config": {"weight_modes": ["log"]},
            "summary": {
                "by_mode": {
                    "log": {"cold_relevant_recall": 0.19, "warm_relevant_recall": 0.44},
                }
            },
        },
    }
    metrics = extract_wce_metrics(payload)
    assert metrics["thread_recall_mean"] == 0.63
    assert metrics["cold_relevant_recall"] == 0.19
    line = format_wce_summary_line(metrics)
    assert "thread=0.63" in line
