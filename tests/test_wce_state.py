"""Unit tests for weekly WCE scheduling helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.wce_state import (
    _resolve_cold_recall_mode,
    extract_wce_metrics,
    format_wce_summary_line,
    wce_conditions,
)


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
    assert metrics["weight_mode"] == "log"
    line = format_wce_summary_line(metrics)
    assert "thread=0.63" in line
    assert "cold_rec=0.19" in line
    assert "mode=log" in line


def test_extract_wce_metrics_variant_labels_cap():
    """Post-#512 payloads use variant_labels + weight_cap, not weight_modes."""
    payload = {
        "timestamp": "20260625T044815Z",
        "handoff": {"summary": {"thread_recall_mean": 0.69}},
        "cold_recall": {
            "config": {"variant_labels": ["cap"], "weight_cap": 1.4},
            "summary": {
                "by_mode": {
                    "cap": {
                        "cold_relevant_recall": 0.1863,
                        "warm_relevant_recall": 0.4661,
                    },
                }
            },
        },
    }
    metrics = extract_wce_metrics(payload)
    assert metrics["weight_mode"] == "cap"
    assert metrics["weight_cap"] == 1.4
    assert metrics["cold_relevant_recall"] == 0.1863
    line = format_wce_summary_line(metrics)
    assert "cold_rec=0.19" in line
    assert "mode=cap@1.4" in line


def test_resolve_cold_recall_mode_from_by_mode_only():
    cold = {"summary": {"by_mode": {"off": {"cold_relevant_recall": 0.2}}}}
    assert _resolve_cold_recall_mode(cold) == "off"


def test_format_wce_summary_includes_curated_pool():
    metrics = {
        "timestamp": "20260625T120000Z",
        "cold_relevant_recall": 0.24,
        "weight_mode": "cap",
        "weight_cap": 1.4,
        "continuity_pool": "curated",
    }
    line = format_wce_summary_line(metrics)
    assert "pool=curated" in line
    assert "mode=cap@1.4" in line
