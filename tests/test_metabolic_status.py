"""Tests for core/metabolic_status.py"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_check_metabolic_status_no_briefing(monkeypatch, tmp_path):
    from core import metabolic_status as ms

    monkeypatch.setattr(ms, "resolve_store_root", lambda: tmp_path)
    monkeypatch.setattr(ms, "fleet_home", lambda: tmp_path)
    monkeypatch.setattr(ms, "_systemd_user_state", lambda _u: "missing")

    status = ms.check_metabolic_status()
    assert status["last_briefing"] is None
    assert status["socket"] == "inactive"
    assert status["timer"] == "missing"
    assert status["consecrated"] is False


def test_check_metabolic_status_consecrated_when_timer_and_briefing(
    monkeypatch, tmp_path
):
    from core import metabolic_status as ms

    briefings = tmp_path / "briefings"
    briefings.mkdir()
    db = briefings / "daily.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE records (id TEXT PRIMARY KEY, data TEXT, created TEXT)")
    conn.execute(
        "INSERT INTO records (id, data, created) VALUES (?, ?, ?)",
        ("briefing_2026-06-17", "{}", "2026-06-17T12:00:00+00:00"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(ms, "resolve_store_root", lambda: tmp_path)
    monkeypatch.setattr(ms, "fleet_home", lambda: tmp_path)
    monkeypatch.setattr(
        ms, "_systemd_user_state", lambda u: "enabled" if "timer" in u else "active"
    )

    status = ms.check_metabolic_status()
    assert status["last_briefing"] == "2026-06-17T12:00:00+00:00"
    assert status["timer"] == "enabled"
    assert status["socket"] == "active"
    assert status["consecrated"] is True


def test_norn_pass_includes_demoted_field():
    from core.metabolic import norn_pass

    report = norn_pass(dry_run=True)
    assert "demoted" in report
