"""Tests for scripts/filesystem_groom_pass.py — filesystem TTL groom."""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from scripts.filesystem_groom_pass import (
    _intake_file_fully_promoted,
    groom_handoffs,
    groom_intake_jsonl,
    groom_pass,
)
from scripts.kart_scripts_sweep import AUTO_RE, sweep_kart_scripts


def test_groom_kart_auto_delete(tmp_path, monkeypatch):
    kart_dir = tmp_path / ".kart-scripts"
    kart_dir.mkdir()
    old = kart_dir / "kart_deadbeef01.py"
    old.write_text("# old\n")
    old_mtime = time.time() - (20 * 86400)
    import os

    os.utime(old, (old_mtime, old_mtime))

    monkeypatch.setattr(
        "scripts.kart_scripts_sweep.kart_scripts_dir",
        lambda: kart_dir,
    )
    summary = sweep_kart_scripts(apply=True, days=14)
    assert "kart_deadbeef01.py" in summary["deleted"]
    assert not old.exists()


def test_groom_kart_named_never_deleted(tmp_path, monkeypatch):
    kart_dir = tmp_path / ".kart-scripts"
    kart_dir.mkdir()
    named = kart_dir / "my_probe.py"
    named.write_text("# probe\n")
    old_mtime = time.time() - (90 * 86400)
    import os

    os.utime(named, (old_mtime, old_mtime))
    monkeypatch.setattr(
        "scripts.kart_scripts_sweep.kart_scripts_dir",
        lambda: kart_dir,
    )
    summary = sweep_kart_scripts(apply=True, days=14, report_days=60)
    assert named.exists()
    assert any("my_probe.py" in s for s in summary["stale_named"])


def test_intake_requires_all_promoted(tmp_path):
    path = tmp_path / "2026-01-01.jsonl"
    now = datetime.now(timezone.utc).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    path.write_text(
        json.dumps({"id": "A", "promoted": True, "promote_tier": "knowledge", "created_at": old})
        + "\n"
        + json.dumps({"id": "B", "promoted": False, "created_at": now})
        + "\n"
    )
    ok, latest = _intake_file_fully_promoted(path)
    assert ok is False


def test_groom_intake_archives_when_promoted(tmp_path, monkeypatch):
    intake_root = tmp_path / "intake"
    agent_dir = intake_root / "willow"
    agent_dir.mkdir(parents=True)
    path = agent_dir / "2026-01-01.jsonl"
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    path.write_text(
        json.dumps({"id": "A", "promoted": True, "promote_tier": "knowledge", "created_at": old})
        + "\n"
    )
    archive = tmp_path / "archive"
    monkeypatch.setenv("WILLOW_INTAKE_ROOT", str(intake_root))
    monkeypatch.setenv("WILLOW_GROOM_ARCHIVE_ROOT", str(archive))

    result = groom_intake_jsonl(apply=True, min_days=30)
    assert result["archived"] == 1
    assert not path.exists()
    assert (archive / "intake" / "willow" / "2026-01-01.jsonl").is_file()


def test_groom_handoff_requires_index(tmp_path, monkeypatch):
    handoffs = tmp_path / "handoffs"
    agent_dir = handoffs / "willow"
    agent_dir.mkdir(parents=True)
    md = agent_dir / "session_handoff-2020-01-01_willow.md"
    md.write_text("# SESSION HANDOFF\n")
    old_mtime = time.time() - (200 * 86400)
    import os

    os.utime(md, (old_mtime, old_mtime))

    monkeypatch.setattr(
        "sap.handoff_paths.handoffs_roots",
        lambda: [handoffs],
    )
    monkeypatch.setattr(
        "sap.handoff_paths.handoffs_root",
        lambda: handoffs,
    )
    monkeypatch.setenv("WILLOW_GROOM_ARCHIVE_ROOT", str(tmp_path / "archive"))

    result = groom_handoffs(apply=True)
    assert result["archived"] == 0
    assert md.exists()


def test_groom_handoff_protects_newest(tmp_path, monkeypatch):
    handoffs = tmp_path / "handoffs"
    agent_dir = handoffs / "willow"
    agent_dir.mkdir(parents=True)
    old_md = agent_dir / "session_handoff-2020-01-01_willow.md"
    new_md = agent_dir / "session_handoff-2026-07-01_willow.md"
    old_md.write_text("# SESSION HANDOFF old\n")
    new_md.write_text("# SESSION HANDOFF new\n")
    import os

    os.utime(old_md, (time.time() - 200 * 86400, time.time() - 200 * 86400))
    os.utime(new_md, (time.time(), time.time()))

    db = agent_dir / "handoffs.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE files (id INTEGER PRIMARY KEY, filename TEXT, filepath TEXT,
            file_type TEXT, file_size INTEGER, mtime TEXT);
    """)
    conn.execute(
        "INSERT INTO files (filename, filepath, file_type, file_size, mtime) VALUES (?,?,?,?,?)",
        (old_md.name, str(old_md), "session", 10, "2020-01-01"),
    )
    conn.execute(
        "INSERT INTO files (filename, filepath, file_type, file_size, mtime) VALUES (?,?,?,?,?)",
        (new_md.name, str(new_md), "session", 10, "2026-07-01"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("sap.handoff_paths.handoffs_roots", lambda: [handoffs])
    monkeypatch.setattr("sap.handoff_paths.handoffs_root", lambda: handoffs)
    monkeypatch.setenv("WILLOW_GROOM_ARCHIVE_ROOT", str(tmp_path / "archive"))

    result = groom_handoffs(apply=True)
    assert new_md.exists()
    assert not old_md.exists()
    assert result["archived"] == 1


def test_groom_dry_run_no_writes(tmp_path, monkeypatch):
    kart_dir = tmp_path / ".kart-scripts"
    kart_dir.mkdir()
    old = kart_dir / "kart_cafebabe01.py"
    old.write_text("# x\n")
    import os

    os.utime(old, (time.time() - 20 * 86400, time.time() - 20 * 86400))
    monkeypatch.setattr("scripts.kart_scripts_sweep.kart_scripts_dir", lambda: kart_dir)
    monkeypatch.setenv("WILLOW_INTAKE_ROOT", str(tmp_path / "intake"))
    monkeypatch.setenv("WILLOW_GROOM_ARCHIVE_ROOT", str(tmp_path / "archive"))

    report = groom_pass(dry_run=True, classes=["kart_scripts"])
    assert report["dry_run"] is True
    assert old.exists()
    assert report["classes"]["kart_scripts"]["reported"] >= 0 or report["classes"]["kart_scripts"]["eligible"] >= 1


def test_auto_re_matches_kart_hex_names():
    assert AUTO_RE.match("kart_deadbeef01.py")
    assert AUTO_RE.match("kart-cafebabe01.py")
    assert not AUTO_RE.match("my_probe.py")
