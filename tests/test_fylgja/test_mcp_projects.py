import json
from pathlib import Path

import pytest

from willow.fylgja.mcp_projects import (
    audit_project,
    ensure_registry,
    expand_home,
    load_registry,
    render_claude_permissions,
    render_project_mcp,
    sync_project,
)

PACKAGE_ROOT = Path(__file__).parent.parent.parent


def _setup_repo_template(repo: Path) -> None:
    template = PACKAGE_ROOT / "willow" / "fylgja" / "config" / "mcp.template.json"
    (repo / "willow" / "fylgja" / "config").mkdir(parents=True)
    (repo / "willow" / "fylgja" / "config" / "mcp.template.json").write_bytes(
        template.read_bytes()
    )
    seed = PACKAGE_ROOT / "willow" / "fylgja" / "config" / "mcp_projects.seed.json"
    (repo / "willow" / "fylgja" / "config" / "mcp_projects.seed.json").write_bytes(
        seed.read_bytes()
    )


def test_expand_home():
    home = str(Path.home())
    assert expand_home("{{HOME}}/github/foo") == f"{home}/github/foo"


def test_render_project_mcp_core_profile(tmp_path, monkeypatch):
    repo = tmp_path / "willow-2.0"
    repo.mkdir()
    _setup_repo_template(repo)
    wh = tmp_path / ".willow"
    monkeypatch.setenv("WILLOW_HOME", str(wh))

    entry = {
        "path": str(tmp_path / "dispatches"),
        "agent": "willow",
        "profile": "core",
        "servers": ["willow", "law-gazelle"],
        "ides": ["cursor", "claude"],
    }
    payload = render_project_mcp("DispatchesFromReality", entry, package_root=repo)
    assert set(payload["mcpServers"]) == {"willow", "law-gazelle"}
    assert payload["mcpServers"]["willow"]["env"]["WILLOW_MCP_PROFILE"] == "core"
    assert payload["mcpServers"]["willow"]["env"]["WILLOW_AGENT_NAME"] == "willow"


def test_render_claude_permissions_law_gazelle():
    perms = render_claude_permissions(["willow", "law-gazelle"])
    assert "mcp__law-gazelle__*" in perms["permissions"]["allow"]
    assert "mcp__willow__app_uninstall" in perms["permissions"]["deny"]


def test_sync_and_audit_roundtrip(tmp_path, monkeypatch):
    repo = tmp_path / "willow-2.0"
    repo.mkdir()
    _setup_repo_template(repo)
    wh = tmp_path / ".willow"
    monkeypatch.setenv("WILLOW_HOME", str(wh))

    proj = tmp_path / "dispatches"
    proj.mkdir()
    (proj / ".cursor").mkdir(parents=True, exist_ok=True)

    registry = {
        "version": 1,
        "projects": {
            "test-proj": {
                "path": str(proj),
                "agent": "willow",
                "profile": "core",
                "servers": ["willow"],
                "ides": ["cursor", "claude"],
            }
        },
    }
    reg_path = wh / "mcp" / "projects.json"
    reg_path.parent.mkdir(parents=True)
    reg_path.write_text(json.dumps(registry), encoding="utf-8")

    entry = registry["projects"]["test-proj"]
    sync_project("test-proj", entry, package_root=repo, dry_run=False)
    assert (wh / "mcp" / "test-proj.mcp.json").is_file()
    assert (proj / ".cursor" / "mcp.json").is_file()
    assert (proj / ".mcp.json").is_file()
    assert (proj / ".claude" / "settings.local.json").is_file()

    issues = audit_project("test-proj", entry, package_root=repo)
    assert issues == []


def test_ensure_registry_from_seed(tmp_path, monkeypatch):
    repo = tmp_path / "willow-2.0"
    repo.mkdir()
    _setup_repo_template(repo)
    wh = tmp_path / ".willow"
    monkeypatch.setenv("WILLOW_HOME", str(wh))

    path = ensure_registry(package_root=repo, dry_run=False)
    assert path.is_file()
    data = load_registry(package_root=repo, bootstrap=False)
    assert "willow-2.0" in data["projects"]
    assert "DispatchesFromReality" in data["projects"]
