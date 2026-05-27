"""
claude_plugin.py — Claude Code plugin layout for Fylgja skills.

Claude Code discovers Skill() invocations from:
  willow/fylgja/skills/.claude-plugin/plugin.json
  willow/fylgja/skills/commands/*.md  →  Skill(skill='boot'), etc.

Canonical skill bodies stay at willow/fylgja/skills/<name>.md;
commands/ holds symlinks so doc links and Read() paths stay stable.
"""
from __future__ import annotations

import json
from pathlib import Path

# Skills exposed to Claude Code Skill() — add names here when registering new commands.
CLAUDE_COMMAND_SKILLS: tuple[str, ...] = (
    "boot.md",
    "cold-recovery.md",
    "startup.md",
    "handoff.md",
    "shutdown.md",
)

_PLUGIN_MANIFEST = {
    "name": "fylgja",
    "description": "Willow 2.0 Fylgja behavioral skills — boot, cold-recovery, handoff, startup.",
    "commands": "./commands",
}


def skills_root(package_root: Path) -> Path:
    return package_root / "willow" / "fylgja" / "skills"


def ensure_claude_plugin_layout(package_root: Path, dry_run: bool = False) -> list[str]:
    """
    Write .claude-plugin/plugin.json and commands/<skill>.md symlinks.
    Returns list of actions taken (for dry-run logging).
    """
    root = skills_root(package_root)
    actions: list[str] = []

    manifest_dir = root / ".claude-plugin"
    manifest_path = manifest_dir / "plugin.json"
    manifest_text = json.dumps(_PLUGIN_MANIFEST, indent=2) + "\n"

    if dry_run:
        actions.append(f"Would write {manifest_path}")
    else:
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(manifest_text, encoding="utf-8")
        actions.append(f"Wrote {manifest_path}")

    commands_dir = root / "commands"
    if dry_run:
        actions.append(f"Would ensure {commands_dir}/")
    else:
        commands_dir.mkdir(parents=True, exist_ok=True)

    for filename in CLAUDE_COMMAND_SKILLS:
        src = root / filename
        if not src.is_file():
            actions.append(f"Skip missing {filename}")
            continue
        link = commands_dir / filename
        rel_target = Path("..") / filename
        if dry_run:
            actions.append(f"Would symlink {link} → {rel_target}")
            continue
        if link.is_symlink() or link.is_file():
            link.unlink()
        link.symlink_to(rel_target)
        actions.append(f"Symlinked {link.name} → {rel_target}")

    return actions


def check_claude_plugin_layout(package_root: Path) -> list[str]:
    """Return issue strings if Claude Code skill registration layout is broken."""
    issues: list[str] = []
    root = skills_root(package_root)
    manifest = root / ".claude-plugin" / "plugin.json"
    if not manifest.is_file():
        issues.append("Missing willow/fylgja/skills/.claude-plugin/plugin.json")
        return issues
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as e:
        issues.append(f"Invalid .claude-plugin/plugin.json: {e}")
        return issues
    if not data.get("commands"):
        issues.append(".claude-plugin/plugin.json missing commands path")
    boot_link = root / "commands" / "boot.md"
    boot_src = root / "boot.md"
    if not boot_src.is_file():
        issues.append("Missing willow/fylgja/skills/boot.md")
    elif not boot_link.is_file():
        issues.append("Missing commands/boot.md — run: ./willow agents install <agent> --ide claude")
    elif boot_link.resolve() != boot_src.resolve():
        issues.append("commands/boot.md does not point at skills/boot.md")
    return issues
