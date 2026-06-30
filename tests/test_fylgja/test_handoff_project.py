"""Tests for fleet project resolution and handoff scoping."""

from willow.fylgja.handoff_project import (
    DEFAULT_LEGACY_PROJECT,
    handoff_project_matches,
    resolve_handoff_project,
)


def test_handoff_project_matches_exact():
    assert handoff_project_matches("climate-almanac", "climate-almanac")
    assert not handoff_project_matches("willow-2.0", "climate-almanac")


def test_handoff_project_matches_legacy_default():
    assert handoff_project_matches(None, DEFAULT_LEGACY_PROJECT)
    assert handoff_project_matches("", DEFAULT_LEGACY_PROJECT)
    assert not handoff_project_matches(None, "climate-almanac")


def test_handoff_project_matches_no_filter():
    assert handoff_project_matches("anything", "")
    assert handoff_project_matches(None, "")


def test_resolve_handoff_project_env_override(monkeypatch):
    monkeypatch.setenv("WILLOW_HANDOFF_PROJECT", "custom-project")
    assert resolve_handoff_project() == "custom-project"


def test_resolve_handoff_project_from_registry(monkeypatch, tmp_path):
    willow_repo = tmp_path / "github" / "willow-2.0"
    (willow_repo / "sap").mkdir(parents=True)
    monkeypatch.delenv("WILLOW_HANDOFF_PROJECT", raising=False)
    monkeypatch.delenv("WILLOW_PROJECT_ROOT", raising=False)
    monkeypatch.setattr(
        "willow.fylgja.handoff_project._registry_projects",
        lambda: [(willow_repo.resolve(), "willow-2.0")],
    )
    monkeypatch.chdir(willow_repo / "sap")
    assert resolve_handoff_project(willow_repo / "sap") == "willow-2.0"


def test_resolve_handoff_project_github_slug(monkeypatch, tmp_path):
    github = tmp_path / "github"
    climate = github / "climate-almanac"
    climate.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("WILLOW_HANDOFF_PROJECT", raising=False)
    monkeypatch.delenv("WILLOW_PROJECT_ROOT", raising=False)
    monkeypatch.setattr("willow.fylgja.handoff_project._registry_projects", lambda: [])
    monkeypatch.chdir(climate)
    assert resolve_handoff_project(climate) == "climate-almanac"


def test_resolve_handoff_project_skips_mcp_server_cwd(monkeypatch, tmp_path):
    willow_repo = tmp_path / "github" / "willow-2.0"
    willow_repo.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("WILLOW_MCP_SERVER", "1")
    monkeypatch.delenv("WILLOW_HANDOFF_PROJECT", raising=False)
    monkeypatch.delenv("WILLOW_PROJECT_ROOT", raising=False)
    monkeypatch.setattr("willow.fylgja.handoff_project._registry_projects", lambda: [])
    monkeypatch.chdir(willow_repo)
    assert resolve_handoff_project() == ""


def test_session_anchor_path_project_scoped():
    from willow.fylgja.handoff_project import session_anchor_path

    p = session_anchor_path("willow", "climate-almanac")
    assert p.name == "session_anchor_willow_climate-almanac.json"
    assert session_anchor_path("willow", "").name == "session_anchor_willow.json"


def test_resolve_handoff_project_parent_github_returns_empty(monkeypatch, tmp_path):
    github = tmp_path / "github"
    github.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("WILLOW_HANDOFF_PROJECT", raising=False)
    monkeypatch.delenv("WILLOW_PROJECT_ROOT", raising=False)
    monkeypatch.delenv("WILLOW_MCP_SERVER", raising=False)
    monkeypatch.setattr("willow.fylgja.handoff_project._registry_projects", lambda: [])
    monkeypatch.chdir(github)
    assert resolve_handoff_project(github) == ""


def test_resolve_handoff_project_workspace_param(monkeypatch, tmp_path):
    climate = tmp_path / "github" / "climate-almanac"
    climate.mkdir(parents=True)
    (tmp_path / "github" / "willow-2.0").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("WILLOW_MCP_SERVER", "1")
    monkeypatch.delenv("WILLOW_HANDOFF_PROJECT", raising=False)
    monkeypatch.delenv("WILLOW_PROJECT_ROOT", raising=False)
    monkeypatch.setattr("willow.fylgja.handoff_project._registry_projects", lambda: [])
    monkeypatch.chdir(tmp_path / "github" / "willow-2.0")
    assert resolve_handoff_project(workspace=climate) == "climate-almanac"
