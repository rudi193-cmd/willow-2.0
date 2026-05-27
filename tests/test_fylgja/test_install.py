import json
from pathlib import Path
from willow.fylgja.claude_plugin import check_claude_plugin_layout, ensure_claude_plugin_layout
from willow.fylgja.install import build_hooks_block, apply_hooks, apply_plugin

PACKAGE_ROOT = Path(__file__).parent.parent.parent


def test_build_hooks_block_contains_all_events():
    block = build_hooks_block(PACKAGE_ROOT)
    assert "SessionStart" in block
    assert "UserPromptSubmit" in block
    assert "PreToolUse" in block
    assert "PostToolUse" in block
    assert "Stop" in block


def test_build_hooks_block_points_at_fylgja():
    block = build_hooks_block(PACKAGE_ROOT)
    rendered = json.dumps(block)
    assert "hook_runner" in rendered
    assert "willow.fylgja.events.session_start" in rendered


def test_apply_hooks_dry_run_does_not_write(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {}}))
    apply_hooks(settings_path=settings, package_root=PACKAGE_ROOT, dry_run=True)
    content = json.loads(settings.read_text())
    assert content == {"hooks": {}}


def test_apply_hooks_writes_block(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"model": "sonnet", "hooks": {}}))
    apply_hooks(settings_path=settings, package_root=PACKAGE_ROOT, dry_run=False)
    content = json.loads(settings.read_text())
    assert "SessionStart" in content["hooks"]
    assert content["model"] == "sonnet"


def test_apply_hooks_preserves_non_fylgja_entries(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Read",
                    "hooks": [{"type": "command", "command": "node ~/.markdownai/hooks/preToolUse.mjs"}],
                },
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "/old/path/run_fylgja_hook.py willow.fylgja.events.pre_tool"}],
                },
            ]
        }
    }))
    apply_hooks(settings_path=settings, package_root=PACKAGE_ROOT, dry_run=False)
    content = json.loads(settings.read_text())
    rendered = json.dumps(content["hooks"]["PreToolUse"])
    assert "node ~/.markdownai/hooks/preToolUse.mjs" in rendered
    assert "/old/path/run_fylgja_hook.py" not in rendered


def test_apply_plugin_writes_enabled_plugins(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"model": "sonnet", "enabledPlugins": {}}))
    skills_path = PACKAGE_ROOT / "willow" / "fylgja" / "skills"
    apply_plugin(settings_path=settings, skills_path=skills_path, dry_run=False)
    content = json.loads(settings.read_text())
    assert any("fylgja" in k for k in content["enabledPlugins"])
    assert content["model"] == "sonnet"


def test_apply_plugin_dry_run_does_not_write(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"enabledPlugins": {}}))
    skills_path = PACKAGE_ROOT / "willow" / "fylgja" / "skills"
    apply_plugin(settings_path=settings, skills_path=skills_path, dry_run=True)
    content = json.loads(settings.read_text())
    assert content == {"enabledPlugins": {}}


def test_apply_plugin_replaces_stale_fylgja_plugin(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({
        "enabledPlugins": {
            "fylgja@/home/example/willow-1.9/willow/fylgja/skills": True,
            "other@/tmp/plugin": True,
        }
    }))
    skills_path = PACKAGE_ROOT / "willow" / "fylgja" / "skills"
    apply_plugin(settings_path=settings, skills_path=skills_path, dry_run=False)
    content = json.loads(settings.read_text())
    plugins = content["enabledPlugins"]
    assert "other@/tmp/plugin" in plugins
    assert not any(
        key.endswith("/willow-1.9/willow/fylgja/skills")
        for key in plugins
    )
    assert any(str(skills_path) in key for key in plugins)


def test_claude_plugin_manifest_exists():
    manifest = PACKAGE_ROOT / "willow" / "fylgja" / "skills" / ".claude-plugin" / "plugin.json"
    assert manifest.is_file()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["name"] == "fylgja"
    assert data["commands"] == "./commands"


def test_claude_plugin_boot_command_symlink():
    root = PACKAGE_ROOT / "willow" / "fylgja" / "skills"
    boot_cmd = root / "commands" / "boot.md"
    boot_src = root / "boot.md"
    assert boot_src.is_file()
    assert boot_cmd.is_file()
    assert boot_cmd.resolve() == boot_src.resolve()


def test_check_claude_plugin_layout_ok():
    issues = check_claude_plugin_layout(PACKAGE_ROOT)
    assert issues == []


def test_ensure_claude_plugin_layout_dry_run():
    actions = ensure_claude_plugin_layout(PACKAGE_ROOT, dry_run=True)
    assert any("plugin.json" in a for a in actions)
    assert any("boot.md" in a for a in actions)
