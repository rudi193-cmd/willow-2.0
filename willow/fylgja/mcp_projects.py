"""
mcp_projects.py — Fleet MCP project registry: render + sync per-repo IDE configs.

Registry lives at $WILLOW_HOME/mcp/projects.json (seed: willow/fylgja/config/mcp_projects.seed.json).
IDEs still load folder-specific JSON; this module materializes those files from one source of truth.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from willow.fylgja.install_project import render_mcp_config
from willow.fylgja.project_env import repo_root
from willow.fylgja.willow_home import fleet_home

_HOME_VAR = "{{HOME}}"

# Static MCP server blocks (non-willow). Paths use ${HOME} for IDE expansion.
_STATIC_SERVERS: dict[str, dict[str, Any]] = {
    "law-gazelle": {
        "type": "stdio",
        "command": "python3",
        "args": ["${HOME}/github/safe-app-store/apps/law-gazelle/gazelle_mcp.py"],
    },
    "codebase-memory-mcp": {
        "type": "stdio",
        "command": "${HOME}/.local/bin/codebase-memory-mcp",
        "args": [],
    },
    "courtlistener": {
        "type": "stdio",
        "command": "${HOME}/github/willow-2.0/.venv-dev/bin/python3",
        "args": ["${HOME}/github/courtlistener-mcp/src/server.py"],
    },
}

_DESTRUCTIVE_WILLOW_DENY = [
    "mcp__willow__app_uninstall",
    "mcp__willow__policy_put",
    "mcp__willow__policy_delete",
    "mcp__willow__routine_register",
]


def _package_root() -> Path:
    return repo_root()


def seed_path(package_root: Path | None = None) -> Path:
    root = package_root or _package_root()
    return root / "willow" / "fylgja" / "config" / "mcp_projects.seed.json"


def registry_path(package_root: Path | None = None) -> Path:
    return fleet_home(package_root) / "mcp" / "projects.json"


def expand_home(text: str) -> str:
    home = str(Path.home())
    return text.replace(_HOME_VAR, home).replace("${HOME}", home).replace("$HOME", home)


def expand_home_in_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return expand_home(obj)
    if isinstance(obj, list):
        return [expand_home_in_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {k: expand_home_in_obj(v) for k, v in obj.items()}
    return obj


def _write_json(path: Path, data: dict, *, dry_run: bool) -> None:
    if dry_run:
        print(f"[mcp_projects] Would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    print(f"[mcp_projects] Wrote {path}")


def load_seed(package_root: Path | None = None) -> dict:
    path = seed_path(package_root)
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_registry(*, package_root: Path | None = None, dry_run: bool = False) -> Path:
    """Copy seed → fleet home if projects.json missing."""
    dest = registry_path(package_root)
    if dest.is_file():
        return dest
    seed = load_seed(package_root)
    _write_json(dest, seed, dry_run=dry_run)
    return dest


def load_registry(*, package_root: Path | None = None, bootstrap: bool = True) -> dict:
    path = registry_path(package_root)
    if not path.is_file():
        if bootstrap:
            ensure_registry(package_root=package_root, dry_run=False)
        else:
            raise FileNotFoundError(f"MCP registry missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("projects"), dict):
        raise ValueError(f"Invalid registry (missing projects): {path}")
    return data


def list_projects(*, package_root: Path | None = None) -> list[dict[str, Any]]:
    reg = load_registry(package_root=package_root)
    rows: list[dict[str, Any]] = []
    for pid, entry in sorted(reg.get("projects", {}).items()):
        if not isinstance(entry, dict):
            continue
        rows.append(
            {
                "id": pid,
                "path": entry.get("path", ""),
                "agent": entry.get("agent", ""),
                "profile": entry.get("profile", "standard"),
                "servers": list(entry.get("servers") or []),
                "ides": list(entry.get("ides") or []),
                "note": entry.get("note", ""),
            }
        )
    return rows


def _willow_server_block(
    *,
    agent: str,
    profile: str,
    package_root: Path,
) -> dict[str, Any]:
    config = render_mcp_config(agent, package_root)
    willow = config.get("mcpServers", {}).get("willow")
    if not isinstance(willow, dict):
        raise ValueError("render_mcp_config did not produce willow server")
    env = willow.setdefault("env", {})
    if isinstance(env, dict):
        env["WILLOW_MCP_PROFILE"] = profile
        env.setdefault("WILLOW_INFERENCE_PROVIDER", "auto")
    # Materialized configs use absolute launcher path for out-of-tree repos
    willow["args"] = [expand_home("${HOME}/github/willow-2.0/sap/unified_mcp.sh")]
    return willow


def render_project_mcp(
    project_id: str,
    entry: dict[str, Any],
    *,
    package_root: Path | None = None,
) -> dict[str, Any]:
    root = package_root or _package_root()
    agent = str(entry.get("agent") or "willow").strip()
    profile = str(entry.get("profile") or "standard").strip().lower()
    servers = entry.get("servers") or []
    if not isinstance(servers, list) or not servers:
        raise ValueError(f"project {project_id!r}: servers[] required")

    mcp_servers: dict[str, Any] = {}
    for name in servers:
        if not isinstance(name, str):
            continue
        if name == "willow":
            mcp_servers["willow"] = _willow_server_block(
                agent=agent, profile=profile, package_root=root
            )
        elif name in _STATIC_SERVERS:
            mcp_servers[name] = json.loads(json.dumps(_STATIC_SERVERS[name]))
        else:
            raise ValueError(f"project {project_id!r}: unknown server {name!r}")

    return {"mcpServers": mcp_servers}


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
    # dedupe preserve order
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


def project_paths(project_id: str, entry: dict[str, Any]) -> dict[str, Path]:
    raw = str(entry.get("path") or "").strip()
    if not raw:
        raise ValueError(f"project {project_id!r}: path required")
    root = Path(expand_home(raw)).resolve()
    home_mcp = fleet_home() / "mcp" / f"{project_id}.mcp.json"
    return {
        "root": root,
        "canonical": home_mcp,
        "cursor": root / ".cursor" / "mcp.json",
        "claude_mcp": root / ".mcp.json",
        "claude_settings": root / ".claude" / "settings.local.json",
    }


def _normalize_mcp_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def audit_project(
    project_id: str,
    entry: dict[str, Any],
    *,
    package_root: Path | None = None,
) -> list[str]:
    """Return drift messages (empty = in sync)."""
    issues: list[str] = []
    expected = render_project_mcp(project_id, entry, package_root=package_root)
    paths = project_paths(project_id, entry)
    expected_text = _normalize_mcp_json(expected)

    for label, path in (
        ("canonical", paths["canonical"]),
        ("cursor", paths["cursor"]),
        ("claude_mcp", paths["claude_mcp"]),
    ):
        if not path.is_file():
            issues.append(f"{project_id}: missing {label} → {path}")
            continue
        try:
            on_disk = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            issues.append(f"{project_id}: unreadable {label} ({path}): {e}")
            continue
        if _normalize_mcp_json(on_disk) != expected_text:
            issues.append(f"{project_id}: drift {label} → {path}")

    ides = entry.get("ides") or []
    if "claude" in ides:
        settings = paths["claude_settings"]
        expected_settings = render_claude_permissions(list(entry.get("servers") or []))
        if not settings.is_file():
            issues.append(f"{project_id}: missing claude settings → {settings}")
        else:
            try:
                on_disk = json.loads(settings.read_text(encoding="utf-8"))
            except Exception as e:
                issues.append(f"{project_id}: unreadable claude settings: {e}")
            else:
                for key in ("permissions", "enableAllProjectMcpServers", "enabledMcpjsonServers"):
                    if on_disk.get(key) != expected_settings.get(key):
                        issues.append(
                            f"{project_id}: claude settings drift ({key}) → {settings}"
                        )
                        break

    proj_path = paths["root"]
    if not proj_path.is_dir():
        issues.append(f"{project_id}: path does not exist → {proj_path}")

    return issues


def sync_project(
    project_id: str,
    entry: dict[str, Any],
    *,
    package_root: Path | None = None,
    dry_run: bool = False,
    claude_settings: bool = True,
) -> dict[str, Path]:
    payload = render_project_mcp(project_id, entry, package_root=package_root)
    paths = project_paths(project_id, entry)
    ides = entry.get("ides") or []

    for label, path in (
        ("canonical", paths["canonical"]),
        ("cursor", paths["cursor"] if "cursor" in ides else None),
        ("claude_mcp", paths["claude_mcp"] if "claude" in ides else None),
    ):
        if path is None:
            continue
        _write_json(path, payload, dry_run=dry_run)

    if claude_settings and "claude" in ides:
        settings = render_claude_permissions(list(entry.get("servers") or []))
        _write_json(paths["claude_settings"], settings, dry_run=dry_run)

    return paths


def sync_all(
    *,
    package_root: Path | None = None,
    project_ids: list[str] | None = None,
    dry_run: bool = False,
) -> list[str]:
    reg = load_registry(package_root=package_root)
    projects: dict[str, Any] = reg.get("projects", {})
    selected = project_ids or sorted(projects.keys())
    written: list[str] = []
    for pid in selected:
        entry = projects.get(pid)
        if not isinstance(entry, dict):
            raise KeyError(f"Unknown project {pid!r}")
        sync_project(pid, entry, package_root=package_root, dry_run=dry_run)
        written.append(pid)
    return written


def audit_all(
    *,
    package_root: Path | None = None,
    project_ids: list[str] | None = None,
) -> list[str]:
    reg = load_registry(package_root=package_root)
    projects: dict[str, Any] = reg.get("projects", {})
    selected = project_ids or sorted(projects.keys())
    issues: list[str] = []
    for pid in selected:
        entry = projects.get(pid)
        if not isinstance(entry, dict):
            issues.append(f"Unknown project {pid!r}")
            continue
        issues.extend(audit_project(pid, entry, package_root=package_root))
    return issues


def discover_mcp_json_files(search_root: Path | None = None) -> list[Path]:
    """Best-effort scan for mcp.json / .mcp.json under github (audit helper)."""
    root = search_root or (Path.home() / "github")
    if not root.is_dir():
        return []
    found: list[Path] = []
    for pattern in ("mcp.json", ".mcp.json"):
        for path in root.rglob(pattern):
            parts = set(path.parts)
            if "node_modules" in parts or ".git" in parts:
                continue
            found.append(path.resolve())
    return sorted(found)


def _managed_mcp_paths(*, package_root: Path | None = None) -> set[Path]:
    reg = load_registry(package_root=package_root)
    managed: set[Path] = set()
    for pid, entry in reg.get("projects", {}).items():
        if not isinstance(entry, dict):
            continue
        try:
            paths = project_paths(pid, entry)
            for key in ("canonical", "cursor", "claude_mcp"):
                managed.add(paths[key].resolve())
        except Exception:
            continue
    return managed


def unregistered_mcp_files(
    *,
    package_root: Path | None = None,
    search_root: Path | None = None,
) -> list[Path]:
    """MCP config files on disk not owned by the project registry."""
    managed = _managed_mcp_paths(package_root=package_root)
    skip = {
        Path.home().resolve() / ".cursor" / "mcp.json",
        Path.home().resolve() / ".mcp.json",
    }
    extras: list[Path] = []
    for path in discover_mcp_json_files(search_root):
        resolved = path.resolve()
        if resolved in managed or resolved in skip:
            continue
        parts = resolved.parts
        if "Agents" in parts and "config" in parts:
            continue
        if "agents" in parts and "config" in parts and "mcp.json" in resolved.name:
            continue
        extras.append(resolved)
    return sorted(set(extras))
