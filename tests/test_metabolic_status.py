"""Tests for core/metabolic_status.py"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_check_metabolic_status_no_briefing(monkeypatch, tmp_path):
    from core import metabolic_status as ms

    monkeypatch.setattr(ms, "metabolic_fleet_home", lambda: tmp_path)
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

    briefings = tmp_path / "store" / "briefings"
    briefings.mkdir(parents=True)
    db = briefings / "daily.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE records (id TEXT PRIMARY KEY, data TEXT, created TEXT)")
    conn.execute(
        "INSERT INTO records (id, data, created) VALUES (?, ?, ?)",
        ("briefing_2026-06-17", "{}", "2026-06-17T12:00:00+00:00"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(ms, "metabolic_fleet_home", lambda: tmp_path)
    monkeypatch.setattr(
        ms, "_systemd_user_state", lambda u: "enabled" if "timer" in u else "active"
    )

    status = ms.check_metabolic_status()
    assert status["last_briefing"] == "2026-06-17T12:00:00+00:00"
    assert status["timer"] == "enabled"
    assert status["socket"] == "active"
    assert status["consecrated"] is True


def test_check_metabolic_status_uses_private_home_when_willow_home_is_generated(
    monkeypatch, tmp_path
):
    """Vendored .cursor/mcp.json sets WILLOW_HOME to generated — probe must not lie."""
    from core import metabolic_status as ms
    from willow.fylgja import willow_home as wh

    private = tmp_path / "private"
    private.mkdir()
    (private / "willow.md").write_text("private\n", encoding="utf-8")
    generated = tmp_path / "generated"
    generated.mkdir(parents=True)

    briefings = private / "store" / "briefings"
    briefings.mkdir(parents=True)
    db = briefings / "daily.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE records (id TEXT PRIMARY KEY, data TEXT, created TEXT)")
    conn.execute(
        "INSERT INTO records (id, data, created) VALUES (?, ?, ?)",
        ("briefing_2026-06-25", "{}", "2026-06-25 09:02:42"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("WILLOW_HOME", str(generated))
    monkeypatch.setenv("WILLOW_CONFIG_MODE", "public-fallback")
    monkeypatch.setattr(wh, "private_home", lambda: private)
    monkeypatch.setattr(wh, "private_config_available", lambda: True)
    monkeypatch.setattr(
        ms, "_systemd_user_state", lambda u: "enabled" if "timer" in u else "active"
    )

    status = ms.check_metabolic_status()
    assert status["last_briefing"] == "2026-06-25 09:02:42"
    assert status["consecrated"] is True


def test_norn_pass_includes_demoted_field(mock_norn_subpasses):
    from core.metabolic import norn_pass

    report = norn_pass(dry_run=True)
    assert "demoted" in report
