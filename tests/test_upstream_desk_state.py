"""Unit tests for weekly upstream desk intel scheduling helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.upstream_desk_state import (
    format_upstream_desk_summary_line,
    upstream_desk_conditions,
)


class _FakeStore:
    def __init__(self, state: dict | None = None):
        self._state = state or {}

    def get(self, collection: str, record_id: str):
        if collection == "upstream_steward/desk_intel" and record_id == "state":
            return self._state
        return None


def test_upstream_desk_conditions_due_when_never_run():
    check = upstream_desk_conditions(_FakeStore())
    assert check["should_run"] is True


def test_upstream_desk_conditions_skips_when_recent():
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    check = upstream_desk_conditions(
        _FakeStore({"last_run_at": recent, "cold_count": 9})
    )
    assert check["should_run"] is False
    assert check["cold_count"] == 9


def test_format_upstream_desk_summary_line():
    line = format_upstream_desk_summary_line(
        {
            "last_run_at": "2026-07-12T04:05:00+00:00",
            "thread_count": 205,
            "cold_count": 9,
            "cold_repos": ["openedx/codejail", "coleam00/mcp-mem0"],
        }
    )
    assert "cold=9" in line
    assert "threads=205" in line
    assert "openedx/codejail" in line
