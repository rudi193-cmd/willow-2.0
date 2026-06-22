"""signal_weight_updater.py — unit tests.

Tests weight formula, time-decay, category multipliers, and clamping.
No database required.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from scripts.signal_weight_updater import (
    CATEGORY_MULTIPLIER,
    SIGNAL_CATEGORIES,
    WEIGHT_HALF_LIFE_DAYS,
    WEIGHT_MIN,
    _float_or,
    _target_weight,
    _time_decay,
    run,
)


# --- _time_decay ---

def _ago(days: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def test_time_decay_fresh():
    assert _time_decay(_ago(0)) == pytest.approx(1.0, abs=0.01)


def test_time_decay_half_life():
    assert _time_decay(_ago(WEIGHT_HALF_LIFE_DAYS)) == pytest.approx(0.5, abs=0.02)


def test_time_decay_monotonically_decreasing():
    decays = [_time_decay(_ago(d)) for d in [0, 7, 14, 30, 60]]
    for i in range(len(decays) - 1):
        assert decays[i] > decays[i + 1]


def test_time_decay_naive_datetime_does_not_raise():
    naive = datetime.now() - timedelta(days=7)
    result = _time_decay(naive)
    assert 0.0 < result < 1.0


# --- _target_weight ---

def test_target_weight_fresh_correction_above_one():
    w = _target_weight(confidence=0.85, created_at=_ago(0), category="correction")
    assert w > 1.0


def test_target_weight_old_correction_decays():
    fresh = _target_weight(confidence=0.85, created_at=_ago(0), category="correction")
    old = _target_weight(confidence=0.85, created_at=_ago(30), category="correction")
    assert fresh > old


def test_target_weight_floor_is_weight_min():
    # Very old atom with low confidence must not go below WEIGHT_MIN
    very_old = _target_weight(confidence=0.1, created_at=_ago(365), category="preference")
    assert very_old == pytest.approx(WEIGHT_MIN, abs=0.001)


def test_target_weight_correction_beats_confirmation_same_age_confidence():
    corr = _target_weight(0.8, _ago(0), "correction")
    conf = _target_weight(0.8, _ago(0), "confirmation")
    assert corr > conf


def test_target_weight_correction_has_highest_multiplier():
    corr_mult = CATEGORY_MULTIPLIER["correction"]
    for cat, mult in CATEGORY_MULTIPLIER.items():
        assert corr_mult >= mult, f"correction should have highest multiplier, got {cat}={mult}"


# --- SIGNAL_CATEGORIES completeness ---

def test_all_five_categories_present():
    assert set(SIGNAL_CATEGORIES) == {
        "correction", "preference", "confirmation", "scope_redirect", "tool_denial"
    }


def test_all_categories_have_multipliers():
    for cat in SIGNAL_CATEGORIES:
        assert cat in CATEGORY_MULTIPLIER, f"missing multiplier for {cat}"
        assert CATEGORY_MULTIPLIER[cat] >= 1.0, f"{cat} multiplier should be >= 1.0"


# --- combined: confidence × decay × multiplier ---

def test_high_confidence_fresh_beats_high_confidence_stale():
    fresh = _target_weight(0.9, _ago(1), "correction")
    stale = _target_weight(0.9, _ago(WEIGHT_HALF_LIFE_DAYS * 3), "correction")
    assert fresh > stale


def test_low_confidence_stale_at_floor():
    w = _target_weight(0.3, _ago(WEIGHT_HALF_LIFE_DAYS * 4), "scope_redirect")
    assert w == pytest.approx(WEIGHT_MIN, abs=0.001)


def test_float_or_none_uses_default():
    assert _float_or(None, 0.5) == 0.5
    assert _float_or(0.8, 0.5) == 0.8


def test_run_handles_null_confidence_and_weight(monkeypatch, capsys):
    """Regression: NULL confidence/weight from Postgres must not break :.3f formatting."""
    row = ("atom-001", "correction", None, _ago(0), None)

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, *args, **kwargs):
            pass

        def fetchall(self):
            return [row]

    class _Pg:
        conn = type("Conn", (), {"cursor": lambda self: _Cursor(), "commit": lambda self: None})()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("core.pg_bridge.PgBridge", _Pg)
    result = run(dry_run=True)
    assert result["updated"] == 1
    out = capsys.readouterr().out
    assert "conf=0.500" in out
    assert "1.000 →" in out
