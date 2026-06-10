"""
project_env.py — Repo root, agent identity, and MCP env resolution for all IDE hooks.

Single source of truth for Fylgja wiring (Cursor, Claude Code, Codex, seed).
No silent agent defaults.
"""
from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

FYLGJA_CONFIG = Path("willow") / "fylgja" / "config"
FYLGJA_BIN = Path("willow") / "fylgja" / "bin" / "fylgja-hook"
ACTIVE_AGENT_FILE = Path(".willow") / "active-agent"


def repo_root(start: Path | None = None) -> Path:
    """Resolve willow-2.0 repo root from cwd, explicit path, or this file."""
    if start is not None:
        p = start.resolve()
        for candidate in (p, *p.parents):
            if (candidate / "willow" / "fylgja" / "project_env.py").is_file():
                return candidate
        raise FileNotFoundError(f"Willow repo root not found from {start}")

    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "willow" / "fylgja" / "project_env.py").is_file():
            return candidate

    here = Path(__file__).resolve()
    for candidate in (here.parent.parent.parent, *here.parents):
        if (candidate / "willow" / "fylgja" / "project_env.py").is_file():
            return candidate

    raise FileNotFoundError("Willow repo root not found")


def agent_config_dir(repo: Path, agent: str) -> Path:
    return repo / "agents" / agent / "config"


def active_agent_path(repo: Path) -> Path:
    return repo / ACTIVE_AGENT_FILE


def read_active_agent(repo: Path) -> str:
    path = active_agent_path(repo)
    if path.is_file():
        name = path.read_text(encoding="utf-8").strip()
        if name:
            return name
    return ""


def write_active_agent(repo: Path, agent: str) -> None:
    path = active_agent_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(agent.strip() + "\n", encoding="utf-8")


def list_agent_identities(repo: Path) -> list[str]:
    agents_root = repo / "agents"
    if not agents_root.is_dir():
        return []
    found: list[str] = []
    for child in sorted(agents_root.iterdir()):
        identity = child / "config" / "identity.json"
        if child.is_dir() and identity.is_file():
            found.append(child.name)
    return found


def load_identity_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("WILLOW_AGENT_NAME", "AGENT_NAME"):
        val = data.get(key, "")
        if isinstance(val, str) and val.strip():
            out[key] = val.strip()
    return out


def resolve_agent_name(repo: Path | None = None, hint: str = "") -> str:
    """Resolve agent identity. Raises EnvironmentError if unknown."""
    root = repo or repo_root()
    if hint.strip():
        return hint.strip()

    active = read_active_agent(root)
    if active:
        return active

    for key in ("WILLOW_AGENT_NAME", "AGENT_NAME"):
        val = os.environ.get(key, "").strip()
        if val:
            return val

    agents = list_agent_identities(root)
    if len(agents) == 1:
        return agents[0]

    raise EnvironmentError(
        "WILLOW_AGENT_NAME is not set — run: "
        "python3 -m willow.fylgja.install_project <agent> --ide all"
    )


def mcp_config_paths(repo: Path, agent: str = "") -> list[Path]:
    """Ordered MCP config paths (later entries do not override earlier setdefaults)."""
    paths: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in seen or not path.is_file():
            return
        seen.add(key)
        paths.append(path)

    if agent:
        _add(agent_config_dir(repo, agent) / "mcp.json")
    _add(repo / ".mcp.json")
    _add(repo / ".cursor" / "mcp.json")
    from willow.fylgja.willow_home import willow_home

    _add(willow_home() / "mcp.json")
    return paths


def load_mcp_env(repo: Path | None = None, agent: str = "") -> dict[str, str]:
    root = repo or repo_root()
    if not agent:
        try:
            agent = resolve_agent_name(root)
        except EnvironmentError:
            agent = ""

    out: dict[str, str] = {}
    for path in mcp_config_paths(root, agent):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        willow = data.get("mcpServers", {}).get("willow", {})
        env = willow.get("env") or {}
        if isinstance(env, dict):
            for k, v in env.items():
                if isinstance(v, str):
                    out.setdefault(k, v)
    return out


def merge_hook_env(repo: Path | None = None, agent: str = "") -> dict[str, str]:
    """Full environment for hook subprocesses."""
    root = repo or repo_root()
    merged = os.environ.copy()

    resolved = agent or resolve_agent_name(root)
    identity_path = agent_config_dir(root, resolved) / "identity.json"
    for k, v in load_identity_file(identity_path).items():
        merged.setdefault(k, v)

    for k, v in load_mcp_env(root, resolved).items():
        merged.setdefault(k, v)

    merged["WILLOW_AGENT_NAME"] = resolved
    merged.setdefault("AGENT_NAME", resolved)
    merged.setdefault("GROVE_SENDER", resolved)
    merged.setdefault("GROVE_NAME", resolved)
    merged["WILLOW_ROOT"] = str(root)
    merged["PYTHONPATH"] = str(root)
    return merged


def hook_python(repo: Path) -> Path:
    from willow.fylgja.python_env import willow_python

    return Path(willow_python(repo))


def event_module(module: str) -> str:
    if module.startswith("willow.fylgja.events."):
        return module
    return f"willow.fylgja.events.{module}"


def hook_shell_command(repo: Path, fmt: str, module: str) -> str:
    """Shell command for IDE hook configs (repo-relative fylgja-hook wrapper)."""
    hook = repo / FYLGJA_BIN
    short = module.split(".")[-1] if "." in module else module
    return f"{shlex.quote(str(hook))} {fmt} {short}"


def hook_python_command(repo: Path, fmt: str, module: str) -> str:
    """Absolute hook command for global Claude settings.

    Global Claude hooks run from whichever repo the user opened, so calling
    ``python -m willow...`` directly depends on cwd/PYTHONPATH. Route through
    the repo wrapper instead; it anchors cwd and resolves the active Python.
    """
    return hook_shell_command(repo, fmt, module)
