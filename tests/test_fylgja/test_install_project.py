import json
from pathlib import Path

from willow.fylgja.install_project import install_project, render_mcp_config
from willow.fylgja.project_env import read_active_agent, resolve_agent_name


PACKAGE_ROOT = Path(__file__).parent.parent.parent


def test_render_mcp_preserves_extra_servers(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    template = PACKAGE_ROOT / "willow" / "fylgja" / "config" / "mcp.template.json"
    (repo / "willow" / "fylgja" / "config").mkdir(parents=True)
    (repo / "willow" / "fylgja" / "config" / "mcp.template.json").write_bytes(template.read_bytes())
    (repo / ".mcp.json").write_text(json.dumps({
        "mcpServers": {
            "markdownai": {"command": "node", "args": ["mai.js"]},
            "willow": {"env": {"GROQ_API_KEY": "secret"}},
        }
    }))
    config = render_mcp_config("hanuman", repo)
    assert "markdownai" in config["mcpServers"]
    assert config["mcpServers"]["willow"]["env"]["GROQ_API_KEY"] == "secret"


def test_install_project_dry_run(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    template = PACKAGE_ROOT / "willow" / "fylgja" / "config" / "mcp.template.json"
    (repo / "willow" / "fylgja" / "config").mkdir(parents=True)
    (repo / "willow" / "fylgja" / "config" / "mcp.template.json").write_bytes(template.read_bytes())
    install_project(
        agent_name="hanuman",
        ides=["cursor"],
        package_root=repo,
        dry_run=True,
        claude_global=False,
    )
    assert not (repo / "agents" / "hanuman" / "config" / "mcp.json").exists()


def test_resolve_agent_from_active_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    active = repo / ".willow" / "active-agent"
    active.parent.mkdir(parents=True)
    active.write_text("hanuman\n")
    assert resolve_agent_name(repo) == "hanuman"
    assert read_active_agent(repo) == "hanuman"
