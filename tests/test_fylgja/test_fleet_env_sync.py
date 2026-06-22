"""Fleet env WILLOW_AGENT_NAME sync."""
import os

os.environ.setdefault("WILLOW_AGENT_NAME", "willow")

from willow.fylgja.project_env import sync_fleet_env_agent


def test_sync_fleet_env_agent_appends_when_missing(tmp_path, monkeypatch):
    home = tmp_path / "willow-home"
    home.mkdir()
    env_path = home / "env"
    env_path.write_text("WILLOW_ROOT=/tmp/willow-2.0\n", encoding="utf-8")
    monkeypatch.setenv("WILLOW_HOME", str(home))

    assert sync_fleet_env_agent("willow") is True
    assert "WILLOW_AGENT_NAME=willow" in env_path.read_text(encoding="utf-8")
