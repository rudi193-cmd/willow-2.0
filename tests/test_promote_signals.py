"""promote_signals.py — unit tests.

Tests the time-decay formula, weighted-count grouping, per-type config,
and dry-run output without hitting the real store or KB.
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from scripts.promote_signals import (
    HALF_LIFE_DAYS,
    SIGNAL_CONFIGS,
    _content_key,
    _normalize,
    _time_decay,
    _weighted_count,
)


# --- _time_decay ---

def test_time_decay_zero_days():
    now_iso = datetime.now(timezone.utc).isoformat()
    assert _time_decay(now_iso) == pytest.approx(1.0, abs=0.01)


def test_time_decay_half_life():
    past = (datetime.now(timezone.utc) - timedelta(days=HALF_LIFE_DAYS)).isoformat()
    assert _time_decay(past) == pytest.approx(0.5, abs=0.02)


def test_time_decay_two_half_lives():
    past = (datetime.now(timezone.utc) - timedelta(days=HALF_LIFE_DAYS * 2)).isoformat()
    assert _time_decay(past) == pytest.approx(0.25, abs=0.02)


def test_time_decay_bad_iso_returns_one():
    assert _time_decay("not-a-date") == 1.0
    assert _time_decay("") == 1.0


def test_time_decay_is_monotonically_decreasing():
    now = datetime.now(timezone.utc)
    decays = [
        _time_decay((now - timedelta(days=d)).isoformat())
        for d in [0, 7, 14, 30, 60, 90]
    ]
    for i in range(len(decays) - 1):
        assert decays[i] > decays[i + 1]


# --- _weighted_count ---

def test_weighted_count_fresh_record():
    now_iso = datetime.now(timezone.utc).isoformat()
    rec = {"count": 4, "last_seen": now_iso}
    wc = _weighted_count(rec)
    assert wc == pytest.approx(4.0, abs=0.1)


def test_weighted_count_stale_record():
    old_iso = (datetime.now(timezone.utc) - timedelta(days=HALF_LIFE_DAYS)).isoformat()
    rec = {"count": 4, "last_seen": old_iso}
    wc = _weighted_count(rec)
    assert wc == pytest.approx(2.0, abs=0.1)


def test_weighted_count_missing_count_defaults_to_one():
    now_iso = datetime.now(timezone.utc).isoformat()
    rec = {"last_seen": now_iso}
    assert _weighted_count(rec) == pytest.approx(1.0, abs=0.1)


def test_fresh_record_outweighs_stale_same_count():
    now_iso = datetime.now(timezone.utc).isoformat()
    old_iso = (datetime.now(timezone.utc) - timedelta(days=HALF_LIFE_DAYS)).isoformat()
    fresh = {"count": 2, "last_seen": now_iso}
    stale = {"count": 2, "last_seen": old_iso}
    assert _weighted_count(fresh) > _weighted_count(stale)


# --- _content_key ---

def test_content_key_normalizes_text():
    rec = {"content": "  Don't use Bash   for   this  "}
    assert _content_key(rec, "correction") == "don't use bash for this"


def test_content_key_tool_denial_uses_tool_and_reason():
    rec = {"tool_name": "Bash", "reason": "Use MCP instead."}
    key = _content_key(rec, "tool_denial")
    assert key.startswith("Bash|")
    assert "use mcp instead" in key


def test_content_key_tool_denial_different_tools_differ():
    rec_bash = {"tool_name": "Bash", "reason": "Use MCP."}
    rec_write = {"tool_name": "Write", "reason": "Use MCP."}
    assert _content_key(rec_bash, "tool_denial") != _content_key(rec_write, "tool_denial")


# --- SIGNAL_CONFIGS completeness ---

def test_all_five_signal_types_configured():
    expected = {"correction", "preference", "confirmation", "scope_redirect", "tool_denial"}
    assert set(SIGNAL_CONFIGS.keys()) == expected


def test_each_config_has_required_fields():
    for name, cfg in SIGNAL_CONFIGS.items():
        assert cfg.collection.startswith("corpus/"), name
        assert cfg.valence in ("positive", "negative", "neutral"), name
        assert 0.0 < cfg.base_confidence < 1.0, name
        assert cfg.default_min_count >= 1, name


def test_confirmation_is_positive_valence():
    assert SIGNAL_CONFIGS["confirmation"].valence == "positive"


def test_correction_has_highest_base_confidence():
    correction_conf = SIGNAL_CONFIGS["correction"].base_confidence
    for name, cfg in SIGNAL_CONFIGS.items():
        if name != "correction":
            assert correction_conf >= cfg.base_confidence, (
                f"correction ({correction_conf}) should be >= {name} ({cfg.base_confidence})"
            )


# --- time-decay affects promotion ordering ---

def test_stale_high_count_vs_fresh_low_count():
    """A fresh signal with count=2 can outweigh a stale one with count=3."""
    now_iso = datetime.now(timezone.utc).isoformat()
    old_iso = (datetime.now(timezone.utc) - timedelta(days=HALF_LIFE_DAYS * 2)).isoformat()
    fresh = {"count": 2, "last_seen": now_iso}
    stale = {"count": 3, "last_seen": old_iso}
    # stale: 3 × 0.25 = 0.75; fresh: 2 × 1.0 = 2.0
    assert _weighted_count(fresh) > _weighted_count(stale)
