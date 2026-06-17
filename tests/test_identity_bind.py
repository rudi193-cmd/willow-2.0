"""Tests for MCP identity bind (PR 1)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

from willow.fylgja.identity_bind import check_app_id, collect_identity_matrix, identity_bind_mode
from willow.fylgja.install_project import render_mcp_config

PACKAGE_ROOT = Path(__file__).parent.parent


def test_check_app_id_ok_when_match():
    with mock.patch.dict(os.environ, {"WILLOW_AGENT_NAME": "hanuman", "WILLOW_IDENTITY_BIND": "warn"}):
        action, msg = check_app_id("hanuman")
    assert action == "ok"
    assert msg is None


def test_check_app_id_warn_on_mismatch():
    with mock.patch.dict(os.environ, {"WILLOW_AGENT_NAME": "hanuman", "WILLOW_IDENTITY_BIND": "warn"}):
        action, msg = check_app_id("willow")
    assert action == "warn"
    assert msg and "hanuman" in msg


def test_check_app_id_block_in_strict():
    with mock.patch.dict(os.environ, {"WILLOW_AGENT_NAME": "hanuman", "WILLOW_IDENTITY_BIND": "strict"}):
        action, msg = check_app_id("willow")
    assert action == "block"
    assert msg


def test_check_app_id_off_skips():
    with mock.patch.dict(os.environ, {"WILLOW_AGENT_NAME": "hanuman", "WILLOW_IDENTITY_BIND": "off"}):
        action, msg = check_app_id("willow")
    assert action == "ok"


def test_identity_bind_mode_default_warn():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("WILLOW_IDENTITY_BIND", None)
        assert identity_bind_mode() == "warn"


def test_collect_identity_matrix_stale_shell_agent_when_active_matches_disk(tmp_path, monkeypatch):
    """Profile env can lag active-agent; coherence follows disk + active-agent."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".willow").mkdir()
    (repo / ".willow" / "active-agent").write_text("willow\n")
    agent_cfg = repo / "agents" / "willow" / "config"
    agent_cfg.mkdir(parents=True)
    mcp = render_mcp_config("willow", PACKAGE_ROOT)
    (agent_cfg / "mcp.json").write_text(json.dumps(mcp) + "\n")

    monkeypatch.chdir(repo)
    monkeypatch.setenv("WILLOW_AGENT_NAME", "hanuman")

    matrix = collect_identity_matrix(repo)
    assert matrix["coherent"] is True
    assert matrix.get("drift") == []
    assert matrix.get("shell_agent_stale")


def test_sync_fleet_env_agent_updates_env(tmp_path, monkeypatch):
    from willow.fylgja.project_env import sync_fleet_env_agent

    home = tmp_path / "willow-home"
    home.mkdir()
    env_path = home / "env"
    env_path.write_text(
        "WILLOW_ROOT=/tmp/willow-2.0\nWILLOW_AGENT_NAME=hanuman\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("WILLOW_HOME", str(home))

    assert sync_fleet_env_agent("willow") is True
    text = env_path.read_text(encoding="utf-8")
    assert "WILLOW_AGENT_NAME=willow" in text
    assert "WILLOW_AGENT_NAME=hanuman" not in text


def test_collect_identity_matrix_ignores_stale_shell_grove(tmp_path, monkeypatch):
    """Disk MCP is authoritative; profile GROVE_SENDER must not fail coherence."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".willow").mkdir()
    (repo / ".willow" / "active-agent").write_text("hanuman\n")
    agent_cfg = repo / "agents" / "hanuman" / "config"
    agent_cfg.mkdir(parents=True)
    mcp = render_mcp_config("hanuman", PACKAGE_ROOT)
    (agent_cfg / "mcp.json").write_text(json.dumps(mcp) + "\n")

    monkeypatch.chdir(repo)
    monkeypatch.setenv("GROVE_SENDER", "rudi193-cmd")
    monkeypatch.setenv("WILLOW_AGENT_NAME", "hanuman")

    matrix = collect_identity_matrix(repo)
    assert matrix["coherent"] is True
    assert matrix.get("drift") == []
    assert matrix.get("shell_grove_stale")
