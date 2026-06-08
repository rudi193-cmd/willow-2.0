"""
kart_queue.py — Queue shell work for Kart without fragile inline quoting.

Scripts go under {WILLOW_ROOT}/.kart-scripts/ (rw bind in bwrap), not agent /tmp
scratch paths that may be outside mount policy.
"""
from __future__ import annotations

import uuid
from pathlib import Path


def kart_scripts_dir() -> Path:
    """Writable dir inside Kart bwrap bind ({{WILLOW_ROOT}} rw)."""
    try:
        from core.kart_sandbox import willow_repo_root

        root = willow_repo_root()
    except Exception:
        root = None
    if root is None:
        root = Path.home() / "github" / "willow-2.0"
    d = root / ".kart-scripts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def prepare_task_command(
    task: str = "",
    *,
    script_body: str = "",
    script_name: str = "",
) -> tuple[str, str | None]:
    """
    Return (command, script_path).

    If script_body is set, write {WILLOW_ROOT}/.kart-scripts/kart-<id>.py
    and return a command that uses $WILLOW_PYTHON inside Kart.
    Otherwise return task unchanged.
    """
    body = (script_body or "").strip()
    if body:
        name = (script_name or "").strip() or f"kart_{uuid.uuid4().hex[:10]}.py"
        if not name.endswith(".py"):
            name += ".py"
        path = kart_scripts_dir() / name
        path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
        path.chmod(0o755)
        return f'"${{WILLOW_PYTHON:-python3}}" {path}', str(path)
    cmd = (task or "").strip()
    if not cmd:
        raise ValueError("task or script_body required")
    return cmd, None
