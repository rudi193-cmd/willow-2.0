"""
project_wiring.py — Fleet workspace IDE wiring beyond MCP JSON.

Materializes hooks, active-agent, runtime env, and settings for out-of-tree repos
registered in $WILLOW_HOME/mcp/projects.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from willow.fylgja.install_project import (
    _symlink_to,
    canonical_local_settings,
    ensure_canonical_local_settings,
)
from willow.fylgja.project_env import repo_root, write_active_agent
from willow.fylgja.python_env import willow_python
from willow.fylgja.willow_home import fleet_home

_HOME_VAR = "{{HOME}}"

_DESTRUCTIVE_WILLOW_DENY = [
    "mcp__willow__app_uninstall",
    "mcp__willow__policy_put",
    "mcp__willow__policy_delete",
    "mcp__willow__routine_register",
]

_DEFAULT_WIRING: dict[str, Any] = {
    "hooks": True,
    "active_agent": True,
    "cursor_settings": "symlink",
    "claude_settings": "project",
    "python": "fleet",
}

_HOOK_MODULES = (
    ("sessionStart", "session_start", 15),
    ("beforeSubmitPrompt", "prompt_submit", 10),
    ("beforeShellExecution", "pre_tool", 5),
    ("beforeMCPExecution", "pre_tool", 5),
    ("stop", "stop", 30),
)


def expand_home(text: str) -> str:
    home = str(Path.home())
    return text.replace(_HOME_VAR, home).replace("${HOME}", home).replace("$HOME", home)


def _write_json(path: Path, data: dict, *, dry_run: bool) -> None:
    if dry_run:
        print(f"[project_wiring] Would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    print(f"[project_wiring] Wrote {path}")


def render_claude_permissions(servers: list[str]) -> dict[str, Any]:
    allow = [
        "Read(*)",
        "Edit(*)",
        "Write(*)",
        "Glob(*)",
        "Grep(*)",
        "Skill(*)",
        "Task(*)",
    ]
    for name in servers:
        if isinstance(name, str) and name:
            allow.append(f"mcp__{name}__*")
    allow.append("mcp__claude_ai_Grove__*")
    seen: set[str] = set()
    deduped: list[str] = []
    for item in allow:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)

    deny = list(_DESTRUCTIVE_WILLOW_DENY) if "willow" in servers else []
    enabled = [s for s in servers if isinstance(s, str)]
    return {
        "permissions": {"allow": deduped, "deny": deny},
        "enableAllProjectMcpServers": True,
        "enabledMcpjsonServers": enabled,
    }


def normalize_wiring(entry: dict[str, Any]) -> dict[str, Any]:
    if "wiring" not in entry:
        return {k: False for k in _DEFAULT_WIRING}
    raw = entry.get("wiring")
    if raw is False:
        return {k: False for k in _DEFAULT_WIRING}
    if not isinstance(raw, dict):
        return dict(_DEFAULT_WIRING)
    out = dict(_DEFAULT_WIRING)
    out.update(raw)
    return out


def willow_package_root(package_root: Path | None = None) -> Path:
    return package_root or repo_root()


def fleet_hook_bin(package_root: Path | None = None) -> Path:
    return willow_package_root(package_root) / "willow" / "fylgja" / "bin" / "fleet-fylgja-hook"


def render_fleet_cursor_hooks(package_root: Path | None = None) -> dict[str, Any]:
    hook = fleet_hook_bin(package_root).resolve()
    hooks: dict[str, list[dict[str, Any]]] = {}
    for event, module, timeout in _HOOK_MODULES:
        hooks[event] = [
            {
                "command": f"{hook} cursor {module}",
                "timeout": timeout,
            }
        ]
    return {"version": 1, "hooks": hooks}


def runtime_env(agent: str, package_root: Path | None = None) -> dict[str, str]:
    root = willow_package_root(package_root)
    py = willow_python(root)
    home = fleet_home(package_root)
    return {
        "WILLOW_AGENT_NAME": agent,
        "AGENT_NAME": agent,
        "WILLOW_PYTHON": py,
        "WILLOW_ROOT": str(root.resolve()),
        "WILLOW_HOME": str(home.resolve()),
        "PYTHONPATH": str(root.resolve()),
    }


def render_project_claude_settings(
    entry: dict[str, Any],
    *,
    package_root: Path | None = None,
) -> dict[str, Any]:
    agent = str(entry.get("agent") or "willow").strip()
    servers = [s for s in (entry.get("servers") or []) if isinstance(s, str)]
    payload = render_claude_permissions(servers)
    payload["env"] = runtime_env(agent, package_root)
    return payload


def wiring_paths(project_id: str, entry: dict[str, Any]) -> dict[str, Path]:
    raw = str(entry.get("path") or "").strip()
    if not raw:
        raise ValueError(f"project {project_id!r}: path required")
    root = Path(expand_home(raw)).resolve()
    return {
        "root": root,
        "active_agent": root / ".willow" / "active-agent",
        "cursor_hooks": root / ".cursor" / "hooks.json",
        "cursor_settings": root / ".cursor" / "settings.local.json",
        "claude_settings": root / ".claude" / "settings.local.json",
    }


def _normalize_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def audit_project_wiring(
    project_id: str,
    entry: dict[str, Any],
    *,
    package_root: Path | None = None,
) -> list[str]:
    wiring = normalize_wiring(entry)
    if not any(wiring.values()):
        return []

    issues: list[str] = []
    paths = wiring_paths(project_id, entry)
    ides = entry.get("ides") or []
    agent = str(entry.get("agent") or "willow").strip()

    if not paths["root"].is_dir():
        issues.append(f"{project_id}: path does not exist → {paths['root']}")
        return issues

    if wiring.get("active_agent"):
        if not paths["active_agent"].is_file():
            issues.append(f"{project_id}: missing active-agent → {paths['active_agent']}")
        else:
            on_disk = paths["active_agent"].read_text(encoding="utf-8").strip()
            if on_disk != agent:
                issues.append(
                    f"{project_id}: active-agent drift (want {agent!r}, got {on_disk!r})"
                )

    if wiring.get("hooks") and "cursor" in ides:
        expected = render_fleet_cursor_hooks(package_root)
        on_disk = _read_json(paths["cursor_hooks"])
        if on_disk is None:
            issues.append(f"{project_id}: missing cursor hooks → {paths['cursor_hooks']}")
        elif _normalize_json(on_disk) != _normalize_json(expected):
            issues.append(f"{project_id}: cursor hooks drift → {paths['cursor_hooks']}")

    if wiring.get("cursor_settings") == "symlink" and "cursor" in ides:
        canon = canonical_local_settings(agent)
        link = paths["cursor_settings"]
        if not link.is_symlink():
            issues.append(f"{project_id}: cursor settings.local.json should symlink → {canon}")
        elif link.resolve() != canon.resolve():
            issues.append(f"{project_id}: cursor settings symlink target drift → {link}")

    if wiring.get("claude_settings") == "project" and "claude" in ides:
        expected = render_project_claude_settings(entry, package_root=package_root)
        on_disk = _read_json(paths["claude_settings"])
        if on_disk is None:
            issues.append(f"{project_id}: missing claude settings → {paths['claude_settings']}")
        else:
            for key in ("env", "permissions", "enableAllProjectMcpServers", "enabledMcpjsonServers"):
                if on_disk.get(key) != expected.get(key):
                    issues.append(
                        f"{project_id}: claude settings drift ({key}) → {paths['claude_settings']}"
                    )
                    break

    return issues


def sync_project_wiring(
    project_id: str,
    entry: dict[str, Any],
    *,
    package_root: Path | None = None,
    dry_run: bool = False,
) -> None:
    wiring = normalize_wiring(entry)
    if not any(wiring.values()):
        return

    pkg = willow_package_root(package_root)
    paths = wiring_paths(project_id, entry)
    ides = entry.get("ides") or []
    agent = str(entry.get("agent") or "willow").strip()

    paths["root"].mkdir(parents=True, exist_ok=True)

    ensure_canonical_local_settings(agent, pkg, dry_run=dry_run)
    _patch_canonical_runtime_env(agent, pkg, dry_run=dry_run)

    if wiring.get("active_agent"):
        if dry_run:
            print(f"[project_wiring] Would write {paths['active_agent']} → {agent}")
        else:
            write_active_agent(paths["root"], agent)
            print(f"[project_wiring] Wrote {paths['active_agent']}")

    if wiring.get("hooks") and "cursor" in ides:
        payload = render_fleet_cursor_hooks(pkg)
        _write_json(paths["cursor_hooks"], payload, dry_run=dry_run)

    if wiring.get("cursor_settings") == "symlink" and "cursor" in ides:
        canon = canonical_local_settings(agent)
        _symlink_to(paths["cursor_settings"], canon, dry_run)

    if wiring.get("claude_settings") == "project" and "claude" in ides:
        payload = render_project_claude_settings(entry, package_root=pkg)
        _write_json(paths["claude_settings"], payload, dry_run=dry_run)
    elif wiring.get("claude_settings") == "symlink" and "claude" in ides:
        canon = canonical_local_settings(agent)
        _symlink_to(paths["claude_settings"], canon, dry_run)

    hook = pkg / "willow" / "fylgja" / "bin" / "fleet-fylgja-hook"
    if not dry_run and hook.is_file():
        hook.chmod(hook.stat().st_mode | 0o111)


def _patch_canonical_runtime_env(agent: str, package_root: Path, *, dry_run: bool) -> None:
    """Ensure fleet canonical settings carry WILLOW_PYTHON + WILLOW_ROOT."""
    canon = canonical_local_settings(agent)
    if dry_run:
        print(f"[project_wiring] Would patch runtime env in {canon}")
        return
    if canon.is_file():
        try:
            data = json.loads(canon.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
    env = data.setdefault("env", {})
    if not isinstance(env, dict):
        env = {}
        data["env"] = env
    env.update(runtime_env(agent, package_root))
    tmp = canon.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(canon)
