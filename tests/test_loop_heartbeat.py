"""Tests for core/loop_heartbeat.py."""
from __future__ import annotations

import time

import pytest

from core.loop_heartbeat import interval_sec_for, reset_throttle, write, write_throttled
from core.watchmen import check_watchmen


@pytest.fixture
def store_root(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path))
    reset_throttle()
    return tmp_path


def test_write_roundtrips_through_watchmen(store_root):
    assert write("kart_worker", tick_ok=True, lane="fast")
    from core import soil

    status = check_watchmen(soil.get)
    assert status["kart_worker"]["status"] == "ok"


def test_write_throttled_skips_within_interval(store_root, monkeypatch):
    monkeypatch.setattr("core.loop_heartbeat.interval_sec_for", lambda _k: 900)
    assert write_throttled("nest_watcher") is True
    assert write_throttled("nest_watcher") is False


def test_interval_sec_for_kart_worker():
    assert interval_sec_for("kart_worker") == 900


def test_reset_throttle_allows_immediate_rewrite(store_root, monkeypatch):
    monkeypatch.setattr("core.loop_heartbeat.interval_sec_for", lambda _k: 900)
    assert write_throttled("journal_watcher") is True
    reset_throttle("journal_watcher")
    assert write_throttled("journal_watcher") is True
