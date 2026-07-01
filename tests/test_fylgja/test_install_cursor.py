import json
import sqlite3
from pathlib import Path

from sap.handoff_index import handoff_select_sql
from willow.fylgja.install import _is_fylgja_entry
from willow.fylgja.install_project import (
    build_claude_hooks_block,
    install_project,
    render_mcp_config,
)


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


def test_cursor_hooks_template_uses_fylgja_hook():
    path = PACKAGE_ROOT / "willow" / "fylgja" / "config" / "cursor-hooks.json"
    rendered = path.read_text(encoding="utf-8")
    assert "fylgja-hook" in rendered
    assert "session_start" in rendered


def test_build_claude_hooks_block_uses_hook_runner():
    block = build_claude_hooks_block(PACKAGE_ROOT)
    rendered = json.dumps(block)
    assert "fylgja-hook" in rendered
    assert ".venv-dev" not in rendered
    assert "python3 -m willow.fylgja.hook_runner" not in rendered
    assert "SessionStart" in block
    post_matchers = [e.get("matcher", "") for e in block.get("PostToolUse", [])]
    assert "TaskUpdate" in post_matchers


def test_status_strip_hook_is_managed_fylgja_entry():
    entry = {
        "hooks": [
            {
                "type": "command",
                "command": (
                    "/home/sean-campbell/github/willow-2.0/.venv-dev/bin/python3 "
                    "/home/sean-campbell/github/willow-2.0/willow/fylgja/status_strip.py"
                ),
            }
        ]
    }
    assert _is_fylgja_entry(entry)


def test_render_mcp_config_sets_agent_name():
    config = render_mcp_config("hanuman", PACKAGE_ROOT)
    assert config["mcpServers"]["willow"]["env"]["WILLOW_AGENT_NAME"] == "hanuman"


def test_install_project_writes_agent_config(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    wh = tmp_path / "github" / ".willow"
    wh.mkdir(parents=True)
    (wh / "willow.md").write_text("# test\n", encoding="utf-8")
    (wh / "env").write_text("WILLOW_ROOT=\n", encoding="utf-8")
    (wh / "settings.global.json").write_text(
        '{"version":1,"paths":{"willow_root":"","grove_root":"","safe_root":""},"fleet":{"default_agent":""}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("WILLOW_HOME", str(wh))
    for rel in (
        "willow/fylgja/config/mcp.template.json",
        "willow/fylgja/config/cursor-hooks.json",
        "willow/fylgja/config/cursor-cli.json",
        "willow/fylgja/config/claude-settings.json",
        "willow/fylgja/config/codex-mcp.toml.template",
        "willow/fylgja/bin/fylgja-hook",
        "willow/fylgja/project_env.py",
        "willow/fylgja/hook_runner.py",
        "willow/fylgja/install.py",
        "willow/fylgja/install_project.py",
        "willow/fylgja/willow_home.py",
        "willow/fylgja/link_fleet_home.py",
        "willow/fylgja/global_settings.py",
        "scripts/sync_remote_cursor_surface.py",
    ):
        src = PACKAGE_ROOT / rel
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            import shutil
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            dst.write_bytes(src.read_bytes())

    skills_src = PACKAGE_ROOT / "willow" / "fylgja" / "skills"
    skills_dst = repo / "willow" / "fylgja" / "skills"
    if not skills_dst.exists():
        import shutil
        shutil.copytree(skills_src, skills_dst)
    agents_src = PACKAGE_ROOT / "willow" / "fylgja" / "agents" / "rlm-subcall.md"
    agents_dst = repo / "willow" / "fylgja" / "agents" / "rlm-subcall.md"
    agents_dst.parent.mkdir(parents=True, exist_ok=True)
    agents_dst.write_bytes(agents_src.read_bytes())

    install_project(
        agent_name="hanuman",
        ides=["cursor"],
        package_root=repo,
        dry_run=False,
        claude_global=False,
    )

    identity = repo / "agents" / "hanuman" / "config" / "identity.json"
    mcp = repo / "agents" / "hanuman" / "config" / "mcp.json"
    assert identity.is_file()
    assert json.loads(identity.read_text())["WILLOW_AGENT_NAME"] == "hanuman"
    assert mcp.is_file()
    assert (repo / ".willow" / "active-agent").read_text().strip() == "hanuman"
    assert (repo / ".cursor" / "hooks.json").is_file()
    assert not (repo / ".cursor" / "hooks.json").is_symlink()
    assert (repo / ".mcp.json").is_symlink()
    settings_link = repo / ".cursor" / "settings.local.json"
    assert settings_link.is_symlink()
    canon = wh / "agents" / "hanuman" / "settings.local.json"
    assert canon.is_file()
    assert settings_link.resolve() == canon.resolve()
