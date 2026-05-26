"""
events/session_stop.py — Stop hook handler.
Writes SOIL {agent}/stack/current with open tasks, threads, and decisions
so boot step 9 has reliable data even if /shutdown was not run.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.agent_identity import require_agent_name
from willow.fylgja._mcp import call

AGENT = require_agent_name()


def _is_isolated_directory() -> bool:
    mcp = Path.cwd() / ".mcp.json"
    try:
        data = json.loads(mcp.read_text())
        return "willow" not in data.get("mcpServers", {})
    except Exception:
        return False


def _gather_stack() -> dict:
    """Collect open tasks, flags, and overseer initiatives into a stack snapshot."""
    stack: dict = {
        "written_at": datetime.now(timezone.utc).isoformat(),
        "agent": AGENT,
        "open_flags": [],
        "open_initiatives": [],
        "open_tasks": [],
        "source": "session_stop_hook",
    }

    # Open flags
    try:
        flags = call("soil_list", {"app_id": AGENT, "collection": f"{AGENT}/flags"}, timeout=8)
        open_flags = [
            {"title": f.get("title", ""), "fix_path": f.get("fix_path", ""), "severity": f.get("severity", 0)}
            for f in (flags or [])
            if f.get("flag_state") in ("open", "running", "awaiting_authorization")
        ]
        open_flags.sort(key=lambda f: f.get("severity", 0), reverse=True)
        stack["open_flags"] = open_flags[:10]
    except Exception:
        pass

    # Open overseer initiatives
    try:
        initiatives = call("soil_list", {"app_id": AGENT, "collection": f"{AGENT}/overseer"}, timeout=8)
        stack["open_initiatives"] = [
            {"id": i.get("id", ""), "goal": i.get("goal", i.get("title", ""))[:120], "branch": i.get("branch", "")}
            for i in (initiatives or [])
            if i.get("status") != "closed"
        ][:5]
    except Exception:
        pass

    # Recent kart tasks — surface anything pending or running
    try:
        tasks = call("agent_task_list", {"app_id": AGENT}, timeout=8)
        stack["open_tasks"] = [
            {"id": t.get("task_id", t.get("id", "")), "task": t.get("task", "")[:120], "status": t.get("status", "")}
            for t in (tasks or [])
            if t.get("status") in ("pending", "running", "in_progress")
        ][:5]
    except Exception:
        pass

    return stack


def _write_stack(stack: dict) -> bool:
    try:
        call("soil_put", {
            "app_id": AGENT,
            "collection": f"{AGENT}/stack",
            "id": "current",
            "record": stack,
        }, timeout=10)
        return True
    except Exception:
        return False


def main() -> None:
    if _is_isolated_directory():
        sys.exit(0)

    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    stack = _gather_stack()
    ok = _write_stack(stack)

    flag_count = len(stack.get("open_flags", []))
    init_count = len(stack.get("open_initiatives", []))
    task_count = len(stack.get("open_tasks", []))

    msg = (
        f"[STACK] Written to SOIL {AGENT}/stack/current — "
        f"{flag_count} open flags · {init_count} initiatives · {task_count} pending tasks"
    )
    print(json.dumps({"stopReason": msg} if ok else {}))
    sys.exit(0)


if __name__ == "__main__":
    main()
