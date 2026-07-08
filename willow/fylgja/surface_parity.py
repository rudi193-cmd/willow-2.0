"""Cross-IDE surface parity checks — canonical Fylgja vs vendored runtime trees.

Used by scripts/check_ide_parity.py and scripts/sync_remote_cursor_surface.py --check.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REMOTE_SURFACE_DIRS = (".cursor", ".claude", ".agents", ".codex")

_HOOK_MODULE_RE = re.compile(
    r"fylgja-hook\s+(?:cursor|claude|fleet)\s+(\w+)"
    r"|hook_runner.*events\.(\w+)"
    r"|fleet-fylgja-hook\s+cursor\s+(\w+)"
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def fylgja_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "willow" / "fylgja"


def skills_dir(root: Path | None = None) -> Path:
    return fylgja_dir(root) / "skills"


def load_manifest(root: Path | None = None) -> dict[str, Any]:
    path = fylgja_dir(root) / "config" / "ide_surfaces.manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def skill_text(src: Path, skill_name: str) -> str:
    """Match sync_remote_cursor_surface.skill_text for vendored SKILL.md bodies."""
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


def cloud_mcp_json() -> dict[str, Any]:
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
    template = (fylgja_dir() / "config" / "codex-mcp.toml.template").read_text(encoding="utf-8")
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


def _surface_matches_canonical(link: Path, canonical: Path) -> bool:
    if link.is_symlink():
        return link.resolve() == canonical.resolve()
    if not link.is_file() or not canonical.is_file():
        return False
    return link.read_text(encoding="utf-8") == canonical.read_text(encoding="utf-8")


def _parse_hook_module(command: str) -> str | None:
    for group in _HOOK_MODULE_RE.findall(command):
        for part in group:
            if part:
                return part
    return None


def _cursor_hook_modules(hooks_payload: dict) -> dict[str, set[str]]:
    """event -> set of fylgja module names wired on that event."""
    out: dict[str, set[str]] = {}
    for event, entries in (hooks_payload.get("hooks") or {}).items():
        mods: set[str] = set()
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            mod = _parse_hook_module(str(entry.get("command") or ""))
            if mod:
                mods.add(mod)
        if mods:
            out[str(event)] = mods
    return out


def _claude_hook_modules(hooks_payload: dict) -> set[str]:
    mods: set[str] = set()
    for _event, entries in (hooks_payload.get("hooks") or hooks_payload).items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for hook in entry.get("hooks") or []:
                if not isinstance(hook, dict):
                    continue
                mod = _parse_hook_module(str(hook.get("command") or ""))
                if mod:
                    mods.add(mod)
    return mods


def check_hook_parity(root: Path | None = None) -> list[str]:
    """Tier-1 Cursor vs Claude logical hook wiring (canonical templates)."""
    root = root or repo_root()
    manifest = load_manifest(root)
    hook_cfg = manifest.get("hooks") or {}
    required = set(hook_cfg.get("required_modules") or [])
    cursor_required_events = hook_cfg.get("cursor_required_events") or {}

    cursor_path = fylgja_dir(root) / "config" / "cursor-hooks.json"
    try:
        cursor_data = json.loads(cursor_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"hooks: cannot read cursor-hooks.json: {exc}"]

    from willow.fylgja.install_project import build_claude_hooks_block

    claude_block = build_claude_hooks_block(root)
    cursor_by_event = _cursor_hook_modules(cursor_data)
    cursor_modules = set().union(*cursor_by_event.values()) if cursor_by_event else set()
    claude_modules = _claude_hook_modules(claude_block)

    errors: list[str] = []
    for mod in sorted(required):
        if mod not in cursor_modules:
            errors.append(f"hooks: cursor missing module {mod!r} in cursor-hooks.json")
        if mod not in claude_modules:
            errors.append(f"hooks: claude template missing module {mod!r} (build_claude_hooks_block)")

    for event, want_mod in cursor_required_events.items():
        wired = cursor_by_event.get(event) or set()
        if want_mod not in wired:
            errors.append(
                f"hooks: cursor event {event!r} must wire {want_mod!r} "
                f"(regression guard for beforeMCPExecution routing)"
            )

    extra = set(hook_cfg.get("claude_extra_modules") or [])
    for mod in sorted(extra):
        if mod not in claude_modules:
            errors.append(f"hooks: claude template missing optional module {mod!r}")

    return errors


def check_commands_parity(root: Path | None = None) -> list[str]:
    """Command .md files must match across tier-1/2 surfaces."""
    root = root or repo_root()
    manifest = load_manifest(root)
    surfaces = manifest.get("surfaces") or {}
    canonical_dir = skills_dir(root) / "commands"
    if not canonical_dir.is_dir():
        return ["commands: missing canonical willow/fylgja/skills/commands/"]

    canonical = {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted(canonical_dir.glob("*.md"))
    }
    errors: list[str] = []
    for surface_name, meta in surfaces.items():
        if not isinstance(meta, dict) or meta.get("tier", 0) < 1:
            continue
        if not meta.get("commands"):
            continue
        dir_name = f".{surface_name}" if surface_name != "agents" else ".agents"
        cmd_dir = root / dir_name / "commands"
        if not cmd_dir.is_dir():
            errors.append(f"commands: missing {dir_name}/commands/")
            continue
        vendored = {p.name for p in cmd_dir.glob("*.md")}
        if vendored != set(canonical):
            missing = set(canonical) - vendored
            extra = vendored - set(canonical)
            if missing:
                errors.append(f"commands: {dir_name} missing: {', '.join(sorted(missing))}")
            if extra:
                errors.append(f"commands: {dir_name} extra: {', '.join(sorted(extra))}")
            continue
        for name, text in canonical.items():
            got = (cmd_dir / name).read_text(encoding="utf-8")
            if got != text:
                errors.append(
                    f"commands: stale {dir_name}/commands/{name} "
                    f"— run: python3 scripts/sync_remote_cursor_surface.py"
                )
    return errors


def check_skills_matrix(root: Path | None = None) -> list[str]:
    """Every canonical skill body must match on every remote surface."""
    root = root or repo_root()
    errors: list[str] = []
    for src in sorted(skills_dir(root).glob("*.md")):
        name = src.stem
        expected = skill_text(src, name)
        for surface in REMOTE_SURFACE_DIRS:
            dst = root / surface / "skills" / name / "SKILL.md"
            if not dst.is_file():
                errors.append(f"skills-matrix: missing {surface}/skills/{name}/SKILL.md")
                continue
            if dst.read_text(encoding="utf-8") != expected:
                errors.append(
                    f"stale content: {surface}/skills/{name}/SKILL.md "
                    f"— run: python3 scripts/sync_remote_cursor_surface.py"
                )
    return errors


def check_surfaces(root: Path | None = None) -> list[str]:
    """Vendored IDE trees match canonical Fylgja config (surface-drift CI)."""
    root = root or repo_root()
    manifest = load_manifest(root)
    core_skills = manifest.get("core_skills") or []
    errors: list[str] = []

    required = [
        ".cursor/hooks.json",
        ".cursor/cli.json",
        ".cursor/mcp.json",
        ".cursor/permissions.json",
        ".cursor/commands",
        ".cursor/skills",
        ".claude/settings.json",
        ".claude/commands",
        ".claude/skills",
        ".agents/commands",
        ".agents/skills",
        ".codex/config.toml",
        ".codex/commands",
        ".codex/skills",
    ]
    for rel in required:
        path = root / rel
        if not path.exists():
            errors.append(f"missing: {rel}")
        elif path.is_symlink():
            errors.append(f"symlink not allowed: {rel}")

    hooks = root / ".cursor" / "hooks.json"
    if hooks.is_file() and not _surface_matches_canonical(
        hooks, fylgja_dir(root) / "config" / "cursor-hooks.json"
    ):
        errors.append("stale: .cursor/hooks.json")

    cli = root / ".cursor" / "cli.json"
    if cli.is_file() and not _surface_matches_canonical(
        cli, fylgja_dir(root) / "config" / "cursor-cli.json"
    ):
        errors.append("stale: .cursor/cli.json")

    settings = root / ".claude" / "settings.json"
    if settings.is_file() and not _surface_matches_canonical(
        settings, fylgja_dir(root) / "config" / "claude-settings.json"
    ):
        errors.append("stale: .claude/settings.json")

    codex_cfg = root / ".codex" / "config.toml"
    if codex_cfg.is_file():
        text = codex_cfg.read_text(encoding="utf-8")
        if "{{" in text or "}}" in text:
            errors.append("unrendered template placeholders in .codex/config.toml")
        elif text != render_codex_config():
            errors.append("stale: .codex/config.toml")

    mcp = root / ".cursor" / "mcp.json"
    if mcp.is_file():
        try:
            live = json.loads(mcp.read_text(encoding="utf-8"))
            if live != cloud_mcp_json():
                errors.append("stale: .cursor/mcp.json")
        except Exception:
            errors.append("invalid: .cursor/mcp.json")

    for surface in REMOTE_SURFACE_DIRS:
        skills = root / surface / "skills"
        if skills.is_dir():
            count = len(list(skills.glob("*/SKILL.md")))
            if count < 30:
                errors.append(f"too few skills under {surface}/skills ({count})")

    for name in core_skills:
        for surface in REMOTE_SURFACE_DIRS:
            skill = root / surface / "skills" / name / "SKILL.md"
            if not skill.is_file():
                errors.append(f"missing skill: {surface}/skills/{name}/SKILL.md")

    errors.extend(check_skills_matrix(root))
    return errors


def check_live_claude_hooks(root: Path | None = None) -> list[str]:
    """Host ~/.claude/settings.json must carry Fylgja pre_tool (pre-push only)."""
    root = root or repo_root()
    settings = Path.home() / ".claude" / "settings.json"
    if not settings.is_file():
        return ["live-claude: ~/.claude/settings.json missing — run agents install --ide claude"]

    from willow.fylgja.install_project import build_claude_hooks_block

    try:
        live = json.loads(settings.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"live-claude: unreadable ~/.claude/settings.json: {exc}"]

    live_mods = _claude_hook_modules(live)
    template_mods = _claude_hook_modules({"hooks": build_claude_hooks_block(root)})
    required = set(load_manifest(root).get("hooks", {}).get("required_modules") or [])
    errors: list[str] = []
    for mod in sorted(required):
        if mod not in live_mods:
            errors.append(
                f"live-claude: ~/.claude/settings.json missing module {mod!r} "
                f"— run: ./willow.sh agents install <agent> --ide claude"
            )
    if template_mods and not required.issubset(live_mods):
        missing_tpl = template_mods - live_mods
        if missing_tpl - required:
            errors.append(
                f"live-claude: global hooks missing template modules: {sorted(missing_tpl - required)}"
            )
    return errors


def check_live_codex_mcp(root: Path | None = None) -> list[str]:
    """Host ~/.codex/config.toml should include Willow MCP fragment."""
    root = root or repo_root()
    target = Path.home() / ".codex" / "config.toml"
    if not target.is_file():
        return ["live-codex: ~/.codex/config.toml missing — run agents install --ide codex"]
    text = target.read_text(encoding="utf-8")
    if "mcp_servers.willow" not in text or "unified_mcp.sh" not in text:
        return [
            "live-codex: ~/.codex/config.toml missing Willow MCP — "
            "run: ./willow.sh agents install <agent> --ide codex"
        ]
    return []


@dataclass(frozen=True)
class PhaseResult:
    phase: str
    errors: list[str]


PHASES = (
    "surfaces",
    "hooks",
    "commands",
    "skills-matrix",
    "live-claude",
    "live-codex",
)

_PHASE_FUNCS: dict[str, Any] = {
    "surfaces": check_surfaces,
    "hooks": check_hook_parity,
    "commands": check_commands_parity,
    "skills-matrix": check_skills_matrix,
    "live-claude": check_live_claude_hooks,
    "live-codex": check_live_codex_mcp,
}

DEFAULT_CI_PHASES = ("surfaces", "hooks", "commands")


def run_phases(
    phases: list[str] | None = None,
    *,
    root: Path | None = None,
    live: bool = False,
) -> list[PhaseResult]:
    root = root or repo_root()
    selected = list(phases or DEFAULT_CI_PHASES)
    if live:
        for name in ("live-claude", "live-codex"):
            if name not in selected:
                selected.append(name)

    results: list[PhaseResult] = []
    for phase in selected:
        fn = _PHASE_FUNCS.get(phase)
        if fn is None:
            results.append(PhaseResult(phase, [f"unknown phase: {phase}"]))
            continue
        if phase.startswith("live-") and not live:
            continue
        # surfaces already runs skills-matrix; skip duplicate standalone phase
        if phase == "skills-matrix" and "surfaces" in selected:
            continue
        errs = fn(root)
        results.append(PhaseResult(phase, errs))
    return results


def collect_errors(
    phases: list[str] | None = None,
    *,
    root: Path | None = None,
    live: bool = False,
) -> list[str]:
    out: list[str] = []
    for res in run_phases(phases, root=root, live=live):
        out.extend(res.errors)
    return out
