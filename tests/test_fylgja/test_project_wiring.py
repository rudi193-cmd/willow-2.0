import json
from pathlib import Path

from willow.fylgja.mcp_projects import audit_project, sync_project
from willow.fylgja.project_wiring import (
    render_fleet_cursor_hooks,
    render_project_claude_settings,
    sync_project_wiring,
)

PACKAGE_ROOT = Path(__file__).parent.parent.parent


def _setup_repo(repo: Path) -> None:
    template = PACKAGE_ROOT / "willow" / "fylgja" / "config" / "mcp.template.json"
    settings = PACKAGE_ROOT / "willow" / "fylgja" / "config" / "public" / "settings.local.json"
    (repo / "willow" / "fylgja" / "config").mkdir(parents=True)
    (repo / "willow" / "fylgja" / "config" / "mcp.template.json").write_bytes(
        template.read_bytes()
    )
    if settings.is_file():
        (repo / "willow" / "fylgja" / "config" / "settings.local.json").write_bytes(
            settings.read_bytes()
        )
    hook = PACKAGE_ROOT / "willow" / "fylgja" / "bin" / "fleet-fylgja-hook"
    (repo / "willow" / "fylgja" / "bin").mkdir(parents=True)
    (repo / "willow" / "fylgja" / "bin" / "fleet-fylgja-hook").write_bytes(
        hook.read_bytes()
    )


def test_render_fleet_cursor_hooks_absolute(tmp_path):
    repo = tmp_path / "willow-2.0"
    repo.mkdir()
    hook = repo / "willow" / "fylgja" / "bin" / "fleet-fylgja-hook"
    hook.parent.mkdir(parents=True)
    hook.write_text("#!/bin/sh\n", encoding="utf-8")
    payload = render_fleet_cursor_hooks(repo)
    cmd = payload["hooks"]["sessionStart"][0]["command"]
    assert str(hook.resolve()) in cmd
    assert "cursor session_start" in cmd


def test_project_wiring_roundtrip(tmp_path, monkeypatch):
    repo = tmp_path / "willow-2.0"
    repo.mkdir()
    _setup_repo(repo)
    wh = tmp_path / ".willow"
    monkeypatch.setenv("WILLOW_HOME", str(wh))

    proj = tmp_path / "dispatches"
    proj.mkdir()

    entry = {
        "path": str(proj),
        "agent": "willow",
        "profile": "core",
        "servers": ["willow", "law-gazelle"],
        "ides": ["cursor", "claude"],
        "wiring": {
            "hooks": True,
            "active_agent": True,
            "cursor_settings": "symlink",
            "claude_settings": "project",
        },
    }

    reg_path = wh / "mcp" / "projects.json"
    reg_path.parent.mkdir(parents=True)
    reg_path.write_text(
        json.dumps({"version": 1, "projects": {"dispatches": entry}}),
        encoding="utf-8",
    )

    sync_project("dispatches", entry, package_root=repo, dry_run=False)

    assert (proj / ".willow" / "active-agent").read_text(encoding="utf-8").strip() == "willow"
    assert (proj / ".cursor" / "hooks.json").is_file()
    assert (proj / ".cursor" / "settings.local.json").is_symlink()
    claude = json.loads((proj / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    assert claude["env"]["WILLOW_AGENT_NAME"] == "willow"
    assert "mcp__law-gazelle__*" in claude["permissions"]["allow"]

    issues = audit_project("dispatches", entry, package_root=repo)
    assert issues == []


def test_render_project_claude_settings_env(tmp_path, monkeypatch):
    repo = tmp_path / "willow-2.0"
    repo.mkdir()
    _setup_repo(repo)
    wh = tmp_path / ".willow"
    monkeypatch.setenv("WILLOW_HOME", str(wh))

    entry = {
        "agent": "willow",
        "servers": ["willow"],
        "ides": ["claude"],
        "wiring": {"claude_settings": "project"},
    }
    payload = render_project_claude_settings(entry, package_root=repo)
    assert payload["env"]["WILLOW_ROOT"] == str(repo.resolve())
    assert "WILLOW_PYTHON" in payload["env"]
