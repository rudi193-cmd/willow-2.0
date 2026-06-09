#!/usr/bin/env python3
"""Materialize remote-agent discovery files from canonical Fylgja sources.

Cursor cloud agents start from a git checkout and should not depend on local
symlinks into ~/.willow or generated per-agent config. This script vendors the
small discovery surface that remote agents need as real files under project
config directories such as .cursor/, .claude/, .agents/, and .codex/.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FYLGJA = ROOT / "willow" / "fylgja"
SKILLS = FYLGJA / "skills"


def rm_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        rm_path(dst)
    shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        rm_path(dst)
    shutil.copytree(src, dst, symlinks=False)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        rm_path(path)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def skill_text(src: Path, skill_name: str) -> str:
    text = src.read_text(encoding="utf-8")
    if text.startswith("---\n") and "\nname:" in text.split("---", 2)[1]:
        return text
    title = skill_name.replace("-", " ").title()
    return (
        "---\n"
        f"name: {skill_name}\n"
        f"description: Willow Fylgja skill: {title}.\n"
        "---\n\n"
        f"{text}"
    )


def sync_skills(dst_root: Path) -> None:
    if dst_root.exists() or dst_root.is_symlink():
        rm_path(dst_root)
    dst_root.mkdir(parents=True, exist_ok=True)

    for src in sorted(SKILLS.glob("*.md")):
        name = src.stem
        dst = dst_root / name / "SKILL.md"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(skill_text(src, name), encoding="utf-8")

    willow_remote = SKILLS / "commands" / "willow-remote.md"
    if willow_remote.is_file():
        dst = dst_root / "willow-remote" / "SKILL.md"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(skill_text(willow_remote, "willow-remote"), encoding="utf-8")

    rlm = SKILLS / "rlm" / "SKILL.md"
    if rlm.is_file():
        copy_file(rlm, dst_root / "rlm" / "SKILL.md")


def sync_commands(dst_root: Path) -> None:
    if dst_root.exists() or dst_root.is_symlink():
        rm_path(dst_root)
    dst_root.mkdir(parents=True, exist_ok=True)
    for src_root in (FYLGJA / "commands", SKILLS / "commands"):
        if not src_root.is_dir():
            continue
        for src in sorted(src_root.glob("*.md")):
            copy_file(src, dst_root / src.name)


def sync_cursor() -> None:
    cursor = ROOT / ".cursor"
    cursor.mkdir(exist_ok=True)
    copy_file(FYLGJA / "config" / "cursor-hooks.json", cursor / "hooks.json")
    copy_file(FYLGJA / "config" / "cursor-cli.json", cursor / "cli.json")
    sync_commands(cursor / "commands")
    sync_skills(cursor / "skills")
    copy_file(FYLGJA / "agents" / "rlm-subcall.md", cursor / "agents" / "rlm-subcall.md")

    permissions = json.loads((FYLGJA / "config" / "cursor-cli.json").read_text(encoding="utf-8"))
    write_json(cursor / "permissions.json", permissions)

    cloud_mcp = {
        "mcpServers": {
            "willow": {
                "type": "stdio",
                "command": "bash",
                "args": ["sap/unified_mcp.sh"],
                "env": {
                    "WILLOW_AGENT_NAME": "willow",
                    "GROVE_SENDER": "willow",
                    "GROVE_NAME": "willow",
                    "WILLOW_ROOT": ".",
                    "WILLOW_CONFIG_MODE": "public-fallback",
                },
            }
        }
    }
    write_json(cursor / "mcp.json", cloud_mcp)


def sync_claude() -> None:
    claude = ROOT / ".claude"
    (claude / "agents").mkdir(parents=True, exist_ok=True)
    copy_file(FYLGJA / "config" / "claude-settings.json", claude / "settings.json")
    sync_commands(claude / "commands")
    sync_skills(claude / "skills")
    copy_file(FYLGJA / "agents" / "rlm-subcall.md", claude / "agents" / "rlm-subcall.md")


def sync_agents() -> None:
    agents = ROOT / ".agents"
    sync_commands(agents / "commands")
    sync_skills(agents / "skills")
    copy_file(FYLGJA / "agents" / "rlm-subcall.md", agents / "agents" / "rlm-subcall.md")


def sync_codex() -> None:
    codex = ROOT / ".codex"
    sync_commands(codex / "commands")
    sync_skills(codex / "skills")
    copy_file(FYLGJA / "config" / "codex-mcp.toml.template", codex / "config.toml")
    copy_file(FYLGJA / "agents" / "rlm-subcall.md", codex / "agents" / "rlm-subcall.md")


def main() -> int:
    sync_cursor()
    sync_claude()
    sync_agents()
    sync_codex()
    print("Synced remote agent surfaces as real files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
