"""Tests for project-scoped handoff fetch (CLI parity with MCP)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sap.handoff_index import fetch_latest_handoff, handoff_select_sql


def _seed_handoff_db(db_path: Path, agent: str, rows: list[dict]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            mtime TEXT
        );
        CREATE TABLE handoffs (
            file_id INTEGER,
            file_type TEXT,
            handoff_date TEXT,
            summary TEXT,
            open_threads TEXT,
            questions TEXT,
            agreements TEXT,
            capabilities TEXT,
            project TEXT
        );
        """
    )
    for i, row in enumerate(rows, start=1):
        conn.execute(
            "INSERT INTO files (id, filename, mtime) VALUES (?, ?, ?)",
            (i, row["filename"], row.get("mtime", "2026-06-30")),
        )
        conn.execute(
            """
            INSERT INTO handoffs (
                file_id, file_type, handoff_date, summary,
                open_threads, questions, agreements, capabilities, project
            ) VALUES (?, 'session', ?, ?, ?, ?, '[]', '[]', ?)
            """,
            (
                i,
                row.get("date", "2026-06-30"),
                row["summary"],
                json.dumps(row.get("open_threads", [])),
                json.dumps(row.get("questions", [])),
                row.get("project", ""),
            ),
        )
    conn.commit()
    conn.close()


def test_fetch_latest_handoff_project_isolation(monkeypatch, tmp_path):
    """climate-almanac scope must not surface willow-2.0 / Schmidt threads."""
    willow_home = tmp_path / ".willow"
    handoffs = willow_home / "handoffs" / "willow"
    _seed_handoff_db(
        handoffs / "handoffs.db",
        "willow",
        [
            {
                "filename": "session_handoff-2026-06-30a_willow.md",
                "summary": "Schmidt smapply portal entry",
                "project": "willow-2.0",
                "open_threads": ["Schmidt smapply"],
                "mtime": "2026-06-30T20:00:00",
            },
            {
                "filename": "session_handoff-2026-06-30b_willow.md",
                "summary": "Almanac catalog stewards",
                "project": "climate-almanac",
                "open_threads": ["#565 version stewards"],
                "mtime": "2026-06-30T18:00:00",
            },
        ],
    )
    monkeypatch.setenv("WILLOW_HOME", str(willow_home))
    monkeypatch.setenv("WILLOW_HANDOFF_DB", str(handoffs / "handoffs.db"))

    climate = tmp_path / "github" / "climate-almanac"
    climate.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "willow.fylgja.handoff_project._registry_projects",
        lambda: [],
    )

    result = fetch_latest_handoff("willow", workspace=climate)
    assert "error" not in result
    assert result["project"] == "climate-almanac"
    assert "Schmidt" not in result["summary"]
    assert result["open_threads"] == ["#565 version stewards"]


def test_fetch_latest_handoff_missing_project_error(monkeypatch, tmp_path):
    willow_home = tmp_path / ".willow"
    handoffs = willow_home / "handoffs" / "willow"
    _seed_handoff_db(
        handoffs / "handoffs.db",
        "willow",
        [
            {
                "filename": "session_handoff-2026-06-30a_willow.md",
                "summary": "Desk only",
                "project": "willow-2.0",
            },
        ],
    )
    monkeypatch.setenv("WILLOW_HOME", str(willow_home))
    monkeypatch.setenv("WILLOW_HANDOFF_DB", str(handoffs / "handoffs.db"))

    climate = tmp_path / "github" / "climate-almanac"
    climate.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "willow.fylgja.handoff_project._registry_projects",
        lambda: [],
    )

    result = fetch_latest_handoff("willow", workspace=climate)
    assert result.get("error", "").startswith("No session handoffs found for project")
    assert result["project"] == "climate-almanac"


def test_handoff_select_sql_includes_project_column(tmp_path):
    db_path = tmp_path / "handoffs.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE files (id INTEGER PRIMARY KEY, filename TEXT, mtime TEXT);
        CREATE TABLE handoffs (
            file_id INTEGER, file_type TEXT, handoff_date TEXT, summary TEXT,
            open_threads TEXT, questions TEXT, agreements TEXT, capabilities TEXT,
            project TEXT
        );
        """
    )
    sql = handoff_select_sql(conn)
    assert "project" in sql
    conn.close()
