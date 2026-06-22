"""Phase 5A: norn integration — promote_pass() and run() return shapes.

Tests the programmatic entry points without hitting SOIL or Postgres.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from scripts.promote_signals import SIGNAL_CONFIGS, promote_pass
from scripts.signal_weight_updater import run as weight_run


# --- promote_pass return shape ---

def _mock_promote(sig_type, cfg, min_count, dry_run):
    """Fake promote_signal_type that returns (2, 1) for every type."""
    return 2, 1


def test_promote_pass_returns_dict(monkeypatch):
    monkeypatch.setattr("scripts.promote_signals.promote_signal_type", _mock_promote)
    result = promote_pass(dry_run=True)
    assert isinstance(result, dict)
    assert "total_promoted" in result
    assert "total_skipped" in result
    assert "by_type" in result


def test_promote_pass_totals_are_summed(monkeypatch):
    monkeypatch.setattr("scripts.promote_signals.promote_signal_type", _mock_promote)
    result = promote_pass(dry_run=True)
    expected_total = 2 * len(SIGNAL_CONFIGS)
    assert result["total_promoted"] == expected_total
    assert result["total_skipped"] == len(SIGNAL_CONFIGS)


def test_promote_pass_by_type_covers_all_signal_types(monkeypatch):
    monkeypatch.setattr("scripts.promote_signals.promote_signal_type", _mock_promote)
    result = promote_pass(dry_run=True)
    assert set(result["by_type"].keys()) == set(SIGNAL_CONFIGS.keys())


def test_promote_pass_by_type_shape(monkeypatch):
    monkeypatch.setattr("scripts.promote_signals.promote_signal_type", _mock_promote)
    result = promote_pass(dry_run=True)
    for sig_type, counts in result["by_type"].items():
        assert "promoted" in counts
        assert "skipped" in counts


def test_promote_pass_zero_totals_when_nothing_to_promote(monkeypatch):
    monkeypatch.setattr(
        "scripts.promote_signals.promote_signal_type",
        lambda *_a, **_kw: (0, 0),
    )
    result = promote_pass(dry_run=True)
    assert result["total_promoted"] == 0
    assert result["total_skipped"] == 0


def test_promote_pass_dry_run_propagated(monkeypatch):
    calls = []

    def _capture(sig_type, cfg, min_count, dry_run):
        calls.append(dry_run)
        return 0, 0

    monkeypatch.setattr("scripts.promote_signals.promote_signal_type", _capture)
    promote_pass(dry_run=True)
    assert all(calls), "dry_run=True should propagate to every promote_signal_type call"


# --- signal_weight_updater.run() return shape ---

def _fake_pg_bridge_no_rows():
    """PgBridge mock that returns an empty rowset."""
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchall.return_value = []

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    mock_pg = MagicMock()
    mock_pg.__enter__ = lambda s: s
    mock_pg.__exit__ = MagicMock(return_value=False)
    mock_pg.conn = mock_conn
    return mock_pg


def test_weight_run_returns_dict_on_empty(monkeypatch):
    with patch("core.pg_bridge.PgBridge", return_value=_fake_pg_bridge_no_rows()):
        result = weight_run(dry_run=True)
    assert isinstance(result, dict)
    assert result == {"updated": 0, "skipped": 0}


def test_weight_run_has_updated_and_skipped_keys(monkeypatch):
    with patch("core.pg_bridge.PgBridge", return_value=_fake_pg_bridge_no_rows()):
        result = weight_run(dry_run=False)
    assert "updated" in result
    assert "skipped" in result
