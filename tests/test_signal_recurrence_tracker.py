"""signal_recurrence_tracker.py — unit tests.

Tests recurrence detection logic, content-key matching, flag-raising threshold,
double-count prevention, and positive-valence no-flag behavior.
No SOIL or Postgres required.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from scripts.signal_recurrence_tracker import (
    RECURRENCE_THRESHOLD,
    _content_key,
    track_recurrence,
)
from scripts.promote_signals import SIGNAL_CONFIGS


# --- _content_key ---

def test_content_key_normalizes_correction():
    rec = {"content": "  Stop Using Bash  "}
    assert _content_key(rec, "correction") == "stop using bash"


def test_content_key_tool_denial_uses_tool_and_reason():
    rec = {"tool_name": "Bash", "reason": "Use MCP instead"}
    key = _content_key(rec, "tool_denial")
    assert key.startswith("bash|")
    assert "mcp" in key


def test_content_key_empty_content_returns_empty():
    assert _content_key({}, "correction") == ""


def test_content_key_tool_denial_missing_fields_safe():
    key = _content_key({}, "tool_denial")
    assert "|" in key  # still produces key format, just empty halves


# --- track_recurrence return shape ---

def _make_store(promoted_records, unpromoted_records):
    """Build a fake store_port for injection."""
    all_records = promoted_records + unpromoted_records

    store = MagicMock()
    store.list.return_value = all_records
    store.get.return_value = None  # flags don't exist yet
    store.update = MagicMock()
    store.put = MagicMock()
    return store


def _promoted(content: str, rid: str = "promo-001", count: int = 0) -> dict:
    return {
        "id": rid,
        "content": content,
        "promoted": True,
        "promoted_at": "2026-06-01T00:00:00+00:00",
        "recurrence_count": count,
        "recurrence_ids": [],
    }


def _unpromoted(content: str, rid: str = "new-001") -> dict:
    return {"id": rid, "content": content}


def test_track_recurrence_returns_dict():
    with patch("scripts.signal_recurrence_tracker._load_collection", return_value=[]):
        result = track_recurrence(dry_run=True)
    assert isinstance(result, dict)
    assert "total_recurrences" in result
    assert "flags_raised" in result
    assert "by_type" in result


def test_track_recurrence_no_records_returns_zeros():
    with patch("scripts.signal_recurrence_tracker._load_collection", return_value=[]):
        result = track_recurrence(dry_run=True)
    assert result["total_recurrences"] == 0
    assert result["flags_raised"] == 0


def test_track_recurrence_detects_match(monkeypatch):
    promoted = _promoted("stop using bash", "promo-001")
    unpromoted = _unpromoted("stop using bash", "new-002")

    monkeypatch.setattr(
        "scripts.signal_recurrence_tracker._load_collection",
        lambda coll: [promoted, unpromoted],
    )
    store_mock = MagicMock()
    store_mock.update = MagicMock()
    store_mock.put = MagicMock()
    monkeypatch.setattr(
        "core.store_port.get_store_port",
        lambda: store_mock,
    )

    result = track_recurrence(dry_run=True, signal_type_filter="correction")
    assert result["by_type"]["correction"]["recurrences"] == 1


def test_track_recurrence_no_match_returns_zero(monkeypatch):
    promoted = _promoted("stop using bash", "promo-001")
    unpromoted = _unpromoted("something completely different", "new-002")

    monkeypatch.setattr(
        "scripts.signal_recurrence_tracker._load_collection",
        lambda coll: [promoted, unpromoted],
    )
    store_mock = MagicMock()
    monkeypatch.setattr(
        "core.store_port.get_store_port",
        lambda: store_mock,
    )

    result = track_recurrence(dry_run=True, signal_type_filter="correction")
    assert result["by_type"]["correction"]["recurrences"] == 0


def test_flag_raised_at_threshold(monkeypatch):
    # Promoted record already has count = THRESHOLD - 1; one more should trigger
    promoted = _promoted("stop using bash", "promo-001", count=RECURRENCE_THRESHOLD - 1)
    unpromoted = _unpromoted("stop using bash", "new-002")

    monkeypatch.setattr(
        "scripts.signal_recurrence_tracker._load_collection",
        lambda coll: [promoted, unpromoted],
    )
    monkeypatch.setattr("scripts.signal_recurrence_tracker._flag_exists", lambda _: False)
    store_mock = MagicMock()
    store_mock.update = MagicMock()
    store_mock.put = MagicMock()
    monkeypatch.setattr(
        "core.store_port.get_store_port",
        lambda: store_mock,
    )

    result = track_recurrence(dry_run=False, signal_type_filter="correction")
    assert result["by_type"]["correction"]["flags_raised"] >= 1


def test_no_flag_for_positive_valence(monkeypatch):
    # Confirmations recurring should NOT raise flags
    promoted = _promoted("yes exactly perfect", "promo-conf", count=RECURRENCE_THRESHOLD + 1)
    unpromoted = _unpromoted("yes exactly perfect", "new-conf")

    monkeypatch.setattr(
        "scripts.signal_recurrence_tracker._load_collection",
        lambda coll: [promoted, unpromoted],
    )
    store_mock = MagicMock()
    store_mock.update = MagicMock()
    store_mock.put = MagicMock()
    monkeypatch.setattr(
        "core.store_port.get_store_port",
        lambda: store_mock,
    )

    result = track_recurrence(dry_run=True, signal_type_filter="confirmation")
    assert result["by_type"]["confirmation"]["flags_raised"] == 0


def test_already_counted_records_skipped(monkeypatch):
    # recurrence_counted=True records should not trigger another increment
    promoted = _promoted("stop using bash", "promo-001")
    already_counted = {
        "id": "new-already",
        "content": "stop using bash",
        "recurrence_counted": True,
    }

    monkeypatch.setattr(
        "scripts.signal_recurrence_tracker._load_collection",
        lambda coll: [promoted, already_counted],
    )
    store_mock = MagicMock()
    monkeypatch.setattr(
        "core.store_port.get_store_port",
        lambda: store_mock,
    )

    result = track_recurrence(dry_run=True, signal_type_filter="correction")
    assert result["by_type"]["correction"]["recurrences"] == 0


def test_all_signal_types_covered():
    assert set(SIGNAL_CONFIGS.keys()) == {
        "correction", "preference", "confirmation", "scope_redirect", "tool_denial"
    }
