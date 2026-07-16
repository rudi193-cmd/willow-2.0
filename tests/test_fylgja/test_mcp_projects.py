import json
from pathlib import Path

from willow.fylgja.mcp_projects import (
    audit_all,
    audit_project,
    ensure_registry,
    load_registry,
    render_project_mcp,
    sync_app_stubs,
    sync_project,
)
from willow.fylgja.project_wiring import expand_home, render_claude_permissions

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


def test_render_project_mcp_willow_mcp_charter(tmp_path, monkeypatch):
    repo = tmp_path / "willow-2.0"
    repo.mkdir()
    _setup_repo_template(repo)
    wh = tmp_path / ".willow"
    monkeypatch.setenv("WILLOW_HOME", str(wh))

    entry = {
        "path": str(tmp_path / "willow-charter"),
        "agent": "willow",
        "profile": "core",
        "servers": ["willow-mcp", "codebase-memory-mcp"],
        "env": {
            "WILLOW_STORE_ROOT": str(tmp_path / "willow-charter" / ".willow" / "store"),
            "WILLOW_PROJECT_ROOT": str(tmp_path / "willow-charter"),
        },
    }
    payload = render_project_mcp("willow", entry, package_root=repo)
    names = list(payload["mcpServers"])
    assert names[0] == "willow-mcp"
    wm = payload["mcpServers"]["willow-mcp"]
    assert wm["args"] == ["-m", "willow_mcp"]
    assert wm["env"]["WILLOW_APP_ID"] == "willow"
    assert wm["env"]["WILLOW_HUMAN_ORCHESTRATOR"] == "1"


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


def test_render_project_mcp_with_env_overrides(tmp_path, monkeypatch):
    repo = tmp_path / "willow-2.0"
    repo.mkdir()
    _setup_repo_template(repo)
    wh = tmp_path / ".willow"
    monkeypatch.setenv("WILLOW_HOME", str(wh))

    entry = {
        "path": str(tmp_path / "store"),
        "agent": "vishwakarma",
        "profile": "standard",
        "servers": ["willow", "law-gazelle"],
        "env": {"WILLOW_STORE_ROOT": str(tmp_path / "store" / ".willow" / "store")},
        "server_env": {
            "law-gazelle": {"PYTHONPATH": str(tmp_path / "apps" / "law-gazelle")}
        },
    }
    payload = render_project_mcp("safe-app-store", entry, package_root=repo)
    assert payload["mcpServers"]["willow"]["env"]["WILLOW_AGENT_NAME"] == "vishwakarma"
    assert "WILLOW_STORE_ROOT" in payload["mcpServers"]["willow"]["env"]
    assert payload["mcpServers"]["law-gazelle"]["env"]["PYTHONPATH"] == str(
        tmp_path / "apps" / "law-gazelle"
    )


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
    assert "safe-app-store-public" in data["projects"]
    assert "safe-app-store" not in data["projects"]


def test_audit_expands_home_aliases(tmp_path, monkeypatch):
    repo = tmp_path / "willow-2.0"
    repo.mkdir()
    _setup_repo_template(repo)
    stub_tpl = repo / "willow" / "fylgja" / "config" / "mcp_app.stub.json"
    stub_tpl.write_text(
        '{"mcpServers":{"willow":{"type":"stdio","command":"bash","args":["{{HOME}}/sap/unified_mcp.sh"],'
        '"env":{"WILLOW_AGENT_NAME":"{{APP_ID}}","WILLOW_STORE_ROOT":"{{MONOREPO_ROOT}}/.willow/store"}}}}',
        encoding="utf-8",
    )
    wh = tmp_path / ".willow"
    monkeypatch.setenv("WILLOW_HOME", str(wh))

    proj = tmp_path / "store-public"
    proj.mkdir()
    (proj / ".cursor").mkdir(parents=True, exist_ok=True)
    home = str(Path.home())

    registry = {
        "version": 1,
        "projects": {
            "store-public": {
                "path": str(proj),
                "agent": "vishwakarma",
                "profile": "standard",
                "servers": ["willow", "law-gazelle"],
                "ides": ["cursor", "claude"],
                "env": {"WILLOW_STORE_ROOT": f"{home}/github/store-public/.willow/store"},
            }
        },
    }
    reg_path = wh / "mcp" / "projects.json"
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg_path.write_text(json.dumps(registry), encoding="utf-8")

    entry = registry["projects"]["store-public"]
    sync_project("store-public", entry, package_root=repo, dry_run=False)

    # Simulate on-disk absolute path while registry uses ${HOME}
    mcp_path = proj / ".mcp.json"
    on_disk = json.loads(mcp_path.read_text(encoding="utf-8"))
    on_disk["mcpServers"]["law-gazelle"]["args"] = [
        f"{home}/github/safe-app-store-public/apps/law-gazelle/gazelle_mcp.py"
    ]
    mcp_path.write_text(json.dumps(on_disk, indent=2) + "\n", encoding="utf-8")

    issues = audit_project("store-public", entry, package_root=repo)
    assert issues == [], f"expected no drift after home expansion, got {issues}"


def test_sync_app_stubs(tmp_path, monkeypatch):
    repo = tmp_path / "willow-2.0"
    repo.mkdir()
    _setup_repo_template(repo)
    stub_tpl = repo / "willow" / "fylgja" / "config" / "mcp_app.stub.json"
    stub_tpl.write_bytes(
        (PACKAGE_ROOT / "willow" / "fylgja" / "config" / "mcp_app.stub.json").read_bytes()
    )
    wh = tmp_path / ".willow"
    monkeypatch.setenv("WILLOW_HOME", str(wh))

    monorepo = tmp_path / "safe-app-store-public"
    apps = monorepo / "apps" / "ask-jeles"
    apps.mkdir(parents=True)

    entry = {
        "path": str(monorepo),
        "agent": "vishwakarma",
        "profile": "standard",
        "servers": ["willow"],
        "app_stubs": True,
        "env": {"WILLOW_STORE_ROOT": str(monorepo / ".willow" / "store")},
    }
    written = sync_app_stubs("safe-app-store-public", entry, package_root=repo, dry_run=False)
    assert len(written) == 1
    payload = json.loads((apps / ".mcp.json").read_text(encoding="utf-8"))
    assert payload["mcpServers"]["willow"]["env"]["WILLOW_AGENT_NAME"] == "ask-jeles"


def test_audit_all_skips_symlink_alias_roots(tmp_path, monkeypatch):
    repo = tmp_path / "willow-2.0"
    repo.mkdir()
    _setup_repo_template(repo)
    wh = tmp_path / ".willow"
    monkeypatch.setenv("WILLOW_HOME", str(wh))

    canonical = tmp_path / "store-public"
    canonical.mkdir()
    alias = tmp_path / "store-alias"
    alias.symlink_to(canonical, target_is_directory=True)
    (canonical / ".cursor").mkdir(parents=True, exist_ok=True)

    registry = {
        "version": 1,
        "projects": {
            "store-public": {
                "path": str(canonical),
                "agent": "willow",
                "profile": "core",
                "servers": ["willow"],
                "ides": ["cursor", "claude"],
            },
            "store-alias": {
                "path": str(alias),
                "agent": "willow",
                "profile": "core",
                "servers": ["willow"],
                "ides": ["cursor", "claude"],
            },
        },
    }
    reg_path = wh / "mcp" / "projects.json"
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg_path.write_text(json.dumps(registry), encoding="utf-8")

    for pid in ("store-public", "store-alias"):
        sync_project(pid, registry["projects"][pid], package_root=repo, dry_run=False)

    issues = audit_all(package_root=repo)
    assert issues == []
