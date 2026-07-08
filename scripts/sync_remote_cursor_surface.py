#!/usr/bin/env python3
"""Materialize remote-agent discovery files from canonical Fylgja sources.

Cursor cloud agents start from a git checkout and should not depend on local
symlinks into ~/.willow or generated per-agent config. This script vendors the
small discovery surface that remote agents need as real files under project
config directories such as .cursor/, .claude/, .agents/, and .codex/.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FYLGJA = ROOT / "willow" / "fylgja"
SKILLS = FYLGJA / "skills"
REMOTE_SURFACES = (".cursor", ".claude", ".agents", ".codex")


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


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        rm_path(path)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        rm_path(path)
    path.write_text(text, encoding="utf-8")


def skill_text(src: Path, skill_name: str) -> str:
    text = src.read_text(encoding="utf-8")
    mai_line = ""
    body = text
    if body.startswith("@markdownai"):
        head, _, rest = body.partition("\n")
        mai_line = head
        body = rest.lstrip("\n")
    if body.startswith("---\n") and "\nname:" in body.split("---", 2)[1]:
        if not mai_line:
            return text
        # Canonical order for copies: YAML frontmatter first, @markdownai as body line 1.
        _, yaml_block, rest = body.split("---\n", 2)
        return f"---\n{yaml_block}---\n\n{mai_line}\n\n{rest.lstrip()}"
    title = skill_name.replace("-", " ").title()
    prefix = f"{mai_line}\n\n" if mai_line else ""
    return (
        "---\n"
        f"name: {skill_name}\n"
        f"description: Willow Fylgja skill: {title}.\n"
        "---\n\n"
        f"{prefix}{body}"
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


def sync_workspace_skills(workspace_root: Path) -> None:
    """Materialize Willow skills at a parent workspace root.

    Cursor often runs from ~/github while Claude runs from a repo checkout.
    This keeps the skill discovery surface identical without copying hooks,
    MCP config, commands, or settings into the parent workspace.
    """
    workspace_root = workspace_root.expanduser().resolve()
    sync_skills(workspace_root / ".cursor" / "skills")
    sync_skills(workspace_root / ".claude" / "skills")


def sync_commands(dst_root: Path) -> None:
    if dst_root.exists() or dst_root.is_symlink():
        rm_path(dst_root)
    dst_root.mkdir(parents=True, exist_ok=True)
    for src_root in (SKILLS / "commands",):
        if not src_root.is_dir():
            continue
        for src in sorted(src_root.glob("*.md")):
            copy_file(src, dst_root / src.name)


def cloud_mcp_json() -> dict:
    return {
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
                    "WILLOW_HOME": ".willow/generated",
                    "WILLOW_CONFIG_MODE": "public-fallback",
                    "WILLOW_MCP_PROFILE": "standard",
                },
            },
            "codebase-memory-mcp": {
                "type": "stdio",
                "command": "codebase-memory-mcp",
                "args": [],
            },
        }
    }


def render_codex_config(agent: str = "willow") -> str:
    template = (FYLGJA / "config" / "codex-mcp.toml.template").read_text(encoding="utf-8")
    values = {
        "REPO_ROOT": ".",
        "AGENT_NAME": agent,
        "GROVE_ROOT": ".willow/generated/grove",
        "SAFE_ROOT": ".willow/generated/SAFE/Applications",
        "AGENTS_ROOT": ".willow/generated/SAFE/Agents",
        "WILLOW_HOME": ".willow/generated",
        "WILLOW_CONFIG_MODE": "public-fallback",
    }
    out = template
    for key, val in values.items():
        out = out.replace(f"{{{{{key}}}}}", val)
    return out


def sync_cursor() -> None:
    cursor = ROOT / ".cursor"
    cursor.mkdir(exist_ok=True)
    copy_file(FYLGJA / "config" / "cursor-hooks.json", cursor / "hooks.json")
    copy_file(FYLGJA / "config" / "cursor-cli.json", cursor / "cli.json")
    sync_commands(cursor / "commands")
    sync_skills(cursor / "skills")
    copy_file(FYLGJA / "agents" / "rlm-subcall.md", cursor / "agents" / "rlm-subcall.md")
    rules_src = FYLGJA / "rules" / "fylgja-powers.mdc"
    if rules_src.is_file():
        copy_file(rules_src, cursor / "rules" / "fylgja-powers.mdc")

    permissions = json.loads((FYLGJA / "config" / "cursor-cli.json").read_text(encoding="utf-8"))
    write_json(cursor / "permissions.json", permissions)
    write_json(cursor / "mcp.json", cloud_mcp_json())


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
    write_text(codex / "config.toml", render_codex_config())
    copy_file(FYLGJA / "agents" / "rlm-subcall.md", codex / "agents" / "rlm-subcall.md")


def sync_all() -> None:
    sync_cursor()
    sync_claude()
    sync_agents()
    sync_codex()


def _surface_matches_canonical(link: Path, canonical: Path) -> bool:
    if link.is_symlink():
        return link.resolve() == canonical.resolve()
    if not link.is_file() or not canonical.is_file():
        return False
    return link.read_text(encoding="utf-8") == canonical.read_text(encoding="utf-8")


def check_surfaces() -> list[str]:
    from willow.fylgja.surface_parity import check_surfaces as _check

    return _check(ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync or verify remote agent surfaces")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify committed surfaces match canonical Fylgja sources",
    )
    parser.add_argument(
        "--workspace-skills-root",
        type=Path,
        help="Also materialize skills-only .cursor/.claude surfaces at this parent workspace root",
    )
    args = parser.parse_args()
    if args.workspace_skills_root:
        sync_workspace_skills(args.workspace_skills_root)
        print(f"Synced workspace skill surfaces under {args.workspace_skills_root}.")
        return 0
    if args.check:
        errors = check_surfaces()
        if errors:
            print("Remote surface check failed:")
            for err in errors:
                print(f"  - {err}")
            return 1
        print("Remote surface check OK")
        return 0
    sync_all()
    print("Synced remote agent surfaces as real files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
