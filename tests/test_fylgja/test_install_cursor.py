import json
import sqlite3
from pathlib import Path

from sap.handoff_index import handoff_select_sql, select_latest_handoff
from willow.fylgja.install_cursor import build_cursor_hooks_block, apply_cursor_hooks


PACKAGE_ROOT = Path(__file__).parent.parent.parent


def test_handoff_select_sql_tolerates_legacy_schema(tmp_path):
    db = tmp_path / "handoffs.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE files (id INTEGER PRIMARY KEY, filename TEXT, mtime TEXT);
        CREATE TABLE handoffs (
            id INTEGER PRIMARY KEY, file_id INTEGER, file_type TEXT,
            handoff_date TEXT, summary TEXT, open_threads TEXT, questions TEXT,
            raw_content TEXT
        );
    """)
    sql = handoff_select_sql(conn)
    assert "NULL AS agreements" in sql
    assert "NULL AS capabilities" in sql
    conn.close()


def test_handoff_select_sql_includes_v2_columns(tmp_path):
    db = tmp_path / "handoffs.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE files (id INTEGER PRIMARY KEY, filename TEXT, mtime TEXT);
        CREATE TABLE handoffs (
            id INTEGER PRIMARY KEY, file_id INTEGER, agreements TEXT, capabilities TEXT,
            open_threads TEXT, questions TEXT, summary TEXT, handoff_date TEXT, file_type TEXT
        );
    """)
    sql = handoff_select_sql(conn)
    assert "h.agreements" in sql
    assert "h.capabilities" in sql
    conn.close()


def test_build_cursor_hooks_block_contains_core_events():
    block = build_cursor_hooks_block(PACKAGE_ROOT)
    assert block["version"] == 1
    for event in ("sessionStart", "beforeSubmitPrompt", "beforeShellExecution", "stop"):
        assert event in block["hooks"]


def test_build_cursor_hooks_block_points_at_adapter():
    block = build_cursor_hooks_block(PACKAGE_ROOT)
    rendered = json.dumps(block)
    assert "run_cursor_hook.py" in rendered
    assert "willow.fylgja.events.session_start" in rendered


def test_apply_cursor_hooks_writes_block(tmp_path):
    hooks = tmp_path / "hooks.json"
    apply_cursor_hooks(hooks_path=hooks, package_root=PACKAGE_ROOT, dry_run=False)
    content = json.loads(hooks.read_text())
    assert "sessionStart" in content["hooks"]
    assert content["version"] == 1


def test_apply_cursor_hooks_preserves_non_fylgja_entries(tmp_path):
    hooks = tmp_path / "hooks.json"
    hooks.write_text(json.dumps({
        "version": 1,
        "hooks": {
            "stop": [{"command": "notify-send done"}],
        },
    }))
    apply_cursor_hooks(hooks_path=hooks, package_root=PACKAGE_ROOT, dry_run=False)
    content = json.loads(hooks.read_text())
    rendered = json.dumps(content["hooks"]["stop"])
    assert "notify-send done" in rendered
    assert "run_cursor_hook.py" in rendered
