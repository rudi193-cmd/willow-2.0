import json
from pathlib import Path

from willow.fylgja.agents_cli import cmd_check
from willow.fylgja.install_project import export_home_mcp, install_codex, render_mcp_config
from willow.fylgja.willow_home import (
    fleet_home,
    metabolic_fleet_home,
    resolve_secrets_path,
    resolve_store_root,
    willow_home,
    willow_home_alias,
)

PACKAGE_ROOT = Path(__file__).parent.parent.parent


def test_scripts_bridge_handoff_dir_respects_willow_home(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    import importlib
    import scripts.bridge_cross_runtime as bridge

    importlib.reload(bridge)
    assert bridge.HANDOFF_DIR == tmp_path / "handoffs"


def test_sap_inference_secrets_dir_respects_willow_home(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    from sap.core.inference import _secrets_dir

    assert _secrets_dir() == tmp_path / "secrets"


def test_sap_nest_queue_respects_willow_home(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    import importlib
    import sap.core.nest_intake as nest_intake

    importlib.reload(nest_intake)
    assert nest_intake.QUEUE_FILE == tmp_path / "nest-queue.json"


def test_seed_soil_path_respects_willow_home(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    monkeypatch.delenv("WILLOW_STORE_ROOT", raising=False)
    import seed

    assert seed._soil_path("hanuman/cards") == (tmp_path / "store" / "hanuman/cards").resolve()


def test_willow_py_fleet_home_respects_env(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "willow_launcher",
        PACKAGE_ROOT / "willow.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._fleet_home() == tmp_path.resolve()


def test_core_soil_store_respects_willow_home(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    monkeypatch.delenv("WILLOW_STORE_ROOT", raising=False)
    from core.soil import _root

    assert _root() == (tmp_path / "store").resolve()


def test_fylgja_handoff_dir_respects_willow_home(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    from willow.fylgja.handoff_write import handoff_dir

    assert handoff_dir("hanuman") == (tmp_path / "handoffs" / "hanuman").resolve()


def test_willow_home_resolvers(tmp_path, monkeypatch):
    wh = tmp_path / "fleet"
    wh.mkdir()
    monkeypatch.setenv("WILLOW_HOME", str(wh))
    monkeypatch.delenv("WILLOW_STORE_ROOT", raising=False)

    assert willow_home() == wh.resolve()
    assert fleet_home() == wh.resolve()
    assert resolve_store_root() == wh / "store"
    (wh / "secrets.sh").write_text("# test\n", encoding="utf-8")
    assert resolve_secrets_path() == wh / "secrets.sh"
    assert willow_home_alias() == Path.home() / ".willow"


def test_metabolic_fleet_home_prefers_private_when_config_on_disk(
    tmp_path, monkeypatch
):
    generated = tmp_path / "generated"
    generated.mkdir()
    private = tmp_path / "private"
    private.mkdir()
    (private / "willow.md").write_text("private\n", encoding="utf-8")

    monkeypatch.setenv("WILLOW_HOME", str(generated))
    monkeypatch.setenv("WILLOW_CONFIG_MODE", "public-fallback")
    monkeypatch.setattr(
        "willow.fylgja.willow_home.private_home", lambda: private
    )
    monkeypatch.setattr(
        "willow.fylgja.willow_home.private_config_available", lambda: True
    )

    assert fleet_home() == generated.resolve()
    assert metabolic_fleet_home() == private


def test_metabolic_fleet_home_follows_fleet_home_without_private_config(
    tmp_path, monkeypatch
):
    generated = tmp_path / "generated"
    generated.mkdir()
    monkeypatch.setenv("WILLOW_HOME", str(generated))
    monkeypatch.setattr(
        "willow.fylgja.willow_home.private_config_available", lambda: False
    )

    assert metabolic_fleet_home() == generated.resolve()


def test_resolve_store_root_prefers_private_when_config_on_disk(
    tmp_path, monkeypatch
):
    generated = tmp_path / "generated"
    generated.mkdir()
    private = tmp_path / "private"
    private.mkdir()
    (private / "willow.md").write_text("private\n", encoding="utf-8")
    stale_store = tmp_path / "stale" / "store"
    stale_store.mkdir(parents=True)

    monkeypatch.setenv("WILLOW_HOME", str(generated))
    monkeypatch.setenv("WILLOW_CONFIG_MODE", "public-fallback")
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(stale_store))
    monkeypatch.setattr(
        "willow.fylgja.willow_home.private_home", lambda: private
    )
    monkeypatch.setattr(
        "willow.fylgja.willow_home.private_config_available", lambda: True
    )

    assert resolve_store_root() == private / "store"


def test_render_mcp_includes_grove_fields(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    template = PACKAGE_ROOT / "willow" / "fylgja" / "config" / "mcp.template.json"
    (repo / "willow" / "fylgja" / "config").mkdir(parents=True)
    (repo / "willow" / "fylgja" / "config" / "mcp.template.json").write_bytes(
        template.read_bytes()
    )
    env = render_mcp_config("hanuman", repo)["mcpServers"]["willow"]["env"]
    assert env["GROVE_SENDER"] == "hanuman"
    assert env["GROVE_NAME"] == "hanuman"


def test_export_home_mcp_writes_fleet_copy(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    wh = tmp_path / ".willow"
    monkeypatch.setenv("WILLOW_HOME", str(wh))
    template = PACKAGE_ROOT / "willow" / "fylgja" / "config" / "mcp.template.json"
    (repo / "willow" / "fylgja" / "config").mkdir(parents=True)
    (repo / "willow" / "fylgja" / "config" / "mcp.template.json").write_bytes(
        template.read_bytes()
    )
    config = render_mcp_config("willow", repo)
    export_home_mcp("willow", repo, config, dry_run=False)
    dest = wh / "mcp" / "willow-2.0.mcp.json"
    assert dest.is_file()
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["mcpServers"]["willow"]["env"]["GROVE_SENDER"] == "willow"


def test_install_codex_sets_grove_fields(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    template = PACKAGE_ROOT / "willow" / "fylgja" / "config" / "codex-mcp.toml.template"
    (repo / "willow" / "fylgja" / "config").mkdir(parents=True)
    (repo / "willow" / "fylgja" / "config" / "codex-mcp.toml.template").write_bytes(
        template.read_bytes()
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    install_codex("loki", repo, dry_run=False)
    text = (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert 'GROVE_SENDER = "loki"' in text
    assert 'GROVE_NAME = "loki"' in text


def test_agents_check_cursor_skips_claude_global(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".willow").mkdir()
    (repo / ".willow" / "active-agent").write_text("hanuman\n")
    agent_cfg = repo / "agents" / "hanuman" / "config"
    agent_cfg.mkdir(parents=True)
    (agent_cfg / "identity.json").write_text('{"WILLOW_AGENT_NAME":"hanuman"}\n')
    mcp = render_mcp_config("hanuman", PACKAGE_ROOT)
    (agent_cfg / "mcp.json").write_text(json.dumps(mcp) + "\n")

    for rel in (
        "willow/fylgja/bin/fylgja-hook",
        "willow/fylgja/config/kart-sandbox.json",
        "willow/fylgja/config/cursor-hooks.json",
        "willow/fylgja/config/cursor-cli.json",
    ):
        src = PACKAGE_ROOT / rel
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())

    cursor = repo / ".cursor"
    cursor.mkdir()
    (cursor / "hooks.json").write_bytes(
        (repo / "willow/fylgja/config/cursor-hooks.json").read_bytes()
    )
    (cursor / "cli.json").write_bytes(
        (repo / "willow/fylgja/config/cursor-cli.json").read_bytes()
    )
    (cursor / "skills").mkdir()

    monkeypatch.chdir(repo)
    monkeypatch.setattr(
        "willow.fylgja.agents_cli.collect_identity_matrix",
        lambda _root: {"coherent": True, "drift": []},
    )
    monkeypatch.setattr(
        "willow.fylgja.agents_cli._global_claude_has_fylgja_pre_tool",
        lambda: False,
    )
    monkeypatch.setattr("core.kart_sandbox.bwrap_available", lambda: True)

    assert cmd_check(repo, ides=["cursor"]) == 0
