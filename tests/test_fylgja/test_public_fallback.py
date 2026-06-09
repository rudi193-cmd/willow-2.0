import json
from pathlib import Path

import pytest

from willow.fylgja.install_project import ensure_canonical_local_settings, install_project
from willow.fylgja.link_fleet_home import link_fleet_home
from willow.fylgja.willow_home import (
    PUBLIC_FALLBACK_MARKER,
    config_mode,
    fleet_home,
    materialize_public_pack,
    public_pack_dir,
    settings_template_path,
)

PACKAGE_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture
def public_repo(tmp_path, monkeypatch):
    """Minimal repo with public pack, no private willow-config."""
    repo = tmp_path / "repo"
    repo.mkdir()
    pack_src = PACKAGE_ROOT / "willow" / "fylgja" / "config" / "public"
    (repo / "willow" / "fylgja" / "config").mkdir(parents=True)
    import shutil

    shutil.copytree(pack_src, repo / "willow" / "fylgja" / "config" / "public")
    (repo / "willow.md").write_text("# public root contract\n", encoding="utf-8")
    template = PACKAGE_ROOT / "willow" / "fylgja" / "config" / "mcp.template.json"
    (repo / "willow" / "fylgja" / "config" / "mcp.template.json").write_bytes(
        template.read_bytes()
    )
    fake_private = tmp_path / "empty-private"
    fake_private.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("WILLOW_CONFIG_MODE", "public-fallback")
    monkeypatch.delenv("WILLOW_HOME", raising=False)
    (tmp_path / "github").mkdir(exist_ok=True)
    return repo


def test_public_pack_has_no_operator_paths():
    pack = public_pack_dir(PACKAGE_ROOT)
    for path in pack.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "/home/sean-campbell" not in text
            assert "gsk_" not in text


def test_materialize_public_pack(public_repo):
    home = materialize_public_pack(package_root=public_repo)
    assert home == public_repo / ".willow" / "generated"
    assert (home / "willow.md").is_file()
    assert (home / "env").is_file()
    assert (home / "settings.global.json").is_file()
    assert (home / PUBLIC_FALLBACK_MARKER).is_file()
    env_text = (home / "env").read_text(encoding="utf-8")
    assert str(public_repo) in env_text
    assert "GROQ_API_KEY=secret" not in env_text


def test_link_fleet_home_public_fallback(public_repo):
    mode = link_fleet_home(package_root=public_repo)
    assert mode == "public-fallback"
    assert (public_repo / "willow.md").is_file()
    assert not (public_repo / "willow.md").is_symlink()
    assert (public_repo / "willow" / "fylgja" / "config" / "fleet.env").resolve() == (
        public_repo / ".willow" / "generated" / "env"
    )
    assert (public_repo / "willow" / "fylgja" / "config" / "settings.global.json").resolve() == (
        public_repo / ".willow" / "generated" / "settings.global.json"
    )


def test_config_mode_public_when_forced(public_repo):
    assert config_mode(public_repo) == "public-fallback"
    assert fleet_home(public_repo) == public_repo / ".willow" / "generated"


def test_config_mode_respects_explicit_willow_home(tmp_path, monkeypatch):
    wh = tmp_path / "github" / ".willow"
    wh.mkdir(parents=True)
    (wh / "willow.md").write_text("# private test\n", encoding="utf-8")
    monkeypatch.setenv("WILLOW_HOME", str(wh))
    monkeypatch.delenv("WILLOW_CONFIG_MODE", raising=False)

    assert config_mode(tmp_path / "repo") == "private-config"
    assert fleet_home(tmp_path / "repo") == wh.resolve()


def test_settings_template_uses_public_pack(public_repo):
    tpl = settings_template_path(public_repo)
    assert tpl.name == "settings.local.json"
    assert "public" in str(tpl)


def test_install_project_public_dry_run(public_repo):
    link_fleet_home(package_root=public_repo)
    install_project(
        agent_name="willow",
        ides=["cursor"],
        package_root=public_repo,
        dry_run=True,
        claude_global=False,
    )
    canon = ensure_canonical_local_settings("willow", public_repo, dry_run=False)
    data = json.loads(canon.read_text(encoding="utf-8"))
    assert data["env"]["WILLOW_AGENT_NAME"] == "willow"
    assert "enableAllProjectMcpServers" in data
