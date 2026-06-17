"""signal_archive_pass.py — unit tests.

Tests TTL logic, archive criteria, dry-run behavior, and return shape.
No SOIL required.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from scripts.signal_archive_pass import (
    MIN_COUNT_FOR_RETENTION,
    PROMOTED_TTL_DAYS,
    UNPROMOTED_STALE_TTL_DAYS,
    _should_archive_promoted,
    _should_archive_unpromoted,
    archive_pass,
)
from scripts.promote_signals import SIGNAL_CONFIGS


NOW = datetime.now(timezone.utc)


def _days_ago(n: int) -> str:
    return (NOW - timedelta(days=n)).isoformat()


# --- _should_archive_promoted ---

def test_promoted_old_enough_is_archived():
    rec = {"promoted": True, "promoted_at": _days_ago(PROMOTED_TTL_DAYS + 1)}
    assert _should_archive_promoted(rec, NOW) is True


def test_promoted_too_recent_is_kept():
    rec = {"promoted": True, "promoted_at": _days_ago(PROMOTED_TTL_DAYS - 1)}
    assert _should_archive_promoted(rec, NOW) is False


def test_promoted_missing_promoted_at_is_kept():
    rec = {"promoted": True}
    assert _should_archive_promoted(rec, NOW) is False


def test_promoted_exactly_at_boundary_is_archived():
    rec = {"promoted": True, "promoted_at": _days_ago(PROMOTED_TTL_DAYS)}
    assert _should_archive_promoted(rec, NOW) is True


# --- _should_archive_unpromoted ---

def test_unpromoted_stale_low_count_is_archived():
    rec = {"count": 1, "created_at": _days_ago(UNPROMOTED_STALE_TTL_DAYS + 1)}
    assert _should_archive_unpromoted(rec, NOW) is True


def test_unpromoted_stale_but_high_count_is_kept():
    rec = {"count": MIN_COUNT_FOR_RETENTION, "created_at": _days_ago(UNPROMOTED_STALE_TTL_DAYS + 1)}
    assert _should_archive_unpromoted(rec, NOW) is False


def test_unpromoted_fresh_low_count_is_kept():
    rec = {"count": 1, "created_at": _days_ago(UNPROMOTED_STALE_TTL_DAYS - 1)}
    assert _should_archive_unpromoted(rec, NOW) is False


def test_unpromoted_missing_created_at_is_kept():
    rec = {"count": 1}
    assert _should_archive_unpromoted(rec, NOW) is False


# --- archive_pass return shape ---

def _make_store(records):
    store = MagicMock()
    store.list.return_value = records
    store.update = MagicMock()
    return store


def test_archive_pass_returns_dict(monkeypatch):
    monkeypatch.setattr("core.store_port.get_store_port", lambda: _make_store([]))
    result = archive_pass(dry_run=True)
    assert isinstance(result, dict)
    assert "total_archived" in result
    assert "promoted_archived" in result
    assert "stale_archived" in result
    assert "by_type" in result


def test_archive_pass_empty_collections_returns_zeros(monkeypatch):
    monkeypatch.setattr("core.store_port.get_store_port", lambda: _make_store([]))
    result = archive_pass(dry_run=True)
    assert result["total_archived"] == 0


def test_archive_pass_archives_old_promoted(monkeypatch):
    old_promoted = {
        "id": "rec-001",
        "promoted": True,
        "promoted_at": _days_ago(PROMOTED_TTL_DAYS + 10),
    }
    store = _make_store([old_promoted])
    monkeypatch.setattr("core.store_port.get_store_port", lambda: store)
    result = archive_pass(dry_run=False, signal_type_filter="correction")
    assert result["promoted_archived"] >= 1


def test_archive_pass_dry_run_does_not_call_update(monkeypatch):
    old_promoted = {
        "id": "rec-001",
        "promoted": True,
        "promoted_at": _days_ago(PROMOTED_TTL_DAYS + 10),
    }
    store = _make_store([old_promoted])
    monkeypatch.setattr("core.store_port.get_store_port", lambda: store)
    archive_pass(dry_run=True, signal_type_filter="correction")
    store.update.assert_not_called()


def test_archive_pass_skips_already_archived(monkeypatch):
    already_archived = {
        "id": "rec-002",
        "promoted": True,
        "promoted_at": _days_ago(PROMOTED_TTL_DAYS + 10),
        "archived": True,
    }
    store = _make_store([already_archived])
    monkeypatch.setattr("core.store_port.get_store_port", lambda: store)
    result = archive_pass(dry_run=True, signal_type_filter="correction")
    assert result["total_archived"] == 0


def test_archive_pass_covers_all_types(monkeypatch):
    monkeypatch.setattr("core.store_port.get_store_port", lambda: _make_store([]))
    result = archive_pass(dry_run=True)
    assert set(result["by_type"].keys()) == set(SIGNAL_CONFIGS.keys())
