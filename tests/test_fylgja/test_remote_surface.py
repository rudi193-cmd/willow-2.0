from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_cursor_remote_surface_is_materialized():
    required = [
        ".cursor/hooks.json",
        ".cursor/cli.json",
        ".cursor/mcp.json",
        ".cursor/permissions.json",
        ".cursor/commands",
        ".cursor/skills",
        ".cursor/agents/rlm-subcall.md",
    ]
    for rel in required:
        path = ROOT / rel
        assert path.exists(), rel
        assert not path.is_symlink(), rel


def test_core_cursor_skills_are_real_files():
    for name in ("boot", "startup", "handoff", "shutdown", "power", "willow-remote"):
        path = ROOT / ".cursor" / "skills" / name / "SKILL.md"
        assert path.is_file(), name
        assert not path.is_symlink(), name
        text = path.read_text(encoding="utf-8")
        assert f"name: {name}" in text


def test_cursor_commands_include_remote_control():
    path = ROOT / ".cursor" / "commands" / "willow-remote.md"
    assert path.is_file()
    assert not path.is_symlink()
    assert "name: willow-remote" in path.read_text(encoding="utf-8")


def test_claude_compat_surface_is_materialized():
    required = [
        ".claude/settings.json",
        ".claude/commands",
        ".claude/skills",
        ".claude/agents/rlm-subcall.md",
    ]
    for rel in required:
        path = ROOT / rel
        assert path.exists(), rel
        assert not path.is_symlink(), rel


def test_generic_agents_surface_is_materialized():
    required = [
        ".agents/commands",
        ".agents/skills",
        ".agents/agents/rlm-subcall.md",
    ]
    for rel in required:
        path = ROOT / rel
        assert path.exists(), rel
        assert not path.is_symlink(), rel


def test_codex_surface_is_materialized():
    required = [
        ".codex/config.toml",
        ".codex/commands",
        ".codex/skills",
        ".codex/agents/rlm-subcall.md",
    ]
    for rel in required:
        path = ROOT / rel
        assert path.exists(), rel
        assert not path.is_symlink(), rel


def test_all_remote_skill_surfaces_have_core_skills():
    for surface in (".cursor", ".claude", ".agents", ".codex"):
        for name in ("boot", "startup", "handoff", "shutdown", "power", "willow-remote"):
            path = ROOT / surface / "skills" / name / "SKILL.md"
            assert path.is_file(), f"{surface}:{name}"
            assert not path.is_symlink(), f"{surface}:{name}"
            assert f"name: {name}" in path.read_text(encoding="utf-8")
