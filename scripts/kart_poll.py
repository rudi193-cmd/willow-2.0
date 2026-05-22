#!/usr/bin/env python3
"""
kart_poll.py — drain the pending tasks queue at session close.

Wire as a Stop hook in .claude/settings.json alongside session_close.py.
Calls PgBridge directly (no MCP round-trip) so it works even if the
MCP server is down.
"""
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


LIMIT = int(os.environ.get("KART_POLL_LIMIT", "10"))
TIMEOUT = int(os.environ.get("KART_POLL_TIMEOUT", "120"))

_ROUTINE_FIRE_URL = "https://api.anthropic.com/v1/claude_code/routines/{routine_id}/fire"
_ROUTINE_BETA     = "experimental-cc-routine-2026-04-01"


def _run_goal_task(pg, task_id: str, routine_name: str, goal: str):
    """Execute a goal-state task. routine_name maps to a registered Routine.
    If no routine found, fires the goal as a kart_task_submit description for
    a future orchestrator to pick up."""
    import urllib.request, json as _json, time as _time
    started = _time.time()

    routine = None
    try:
        routine = pg.routine_get(routine_name)
    except Exception:
        pass

    if routine:
        # Fire the Routine with the goal as context
        url     = _ROUTINE_FIRE_URL.format(routine_id=routine["id"])
        payload = _json.dumps({"text": goal}).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={
                "Authorization":     f"Bearer {routine['token']}",
                "anthropic-beta":    _ROUTINE_BETA,
                "anthropic-version": "2023-06-01",
                "Content-Type":      "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = _json.loads(resp.read())
            pg.routine_mark_fired(routine_name, body.get("claude_code_session_id", ""))
            return "completed", {
                "type":        "routine_fired",
                "session_id":  body.get("claude_code_session_id"),
                "session_url": body.get("claude_code_session_url"),
                "goal":        goal,
                "elapsed_s":   round(_time.time() - started, 2),
            }
        except Exception as e:
            return "failed", {"error": str(e), "type": "routine_fire_failed", "goal": goal}
    else:
        # No routine registered — log the goal for manual pickup
        return "completed", {
            "type":    "goal_queued",
            "goal":    goal,
            "note":    f"No routine named '{routine_name}' registered. Register via routine_register.",
            "elapsed_s": round(_time.time() - started, 2),
        }


def main() -> int:
    try:
        from core.pg_bridge import PgBridge
        pg = PgBridge()
    except Exception as e:
        print(f"kart_poll: no Postgres ({e}) — skipping", file=sys.stderr)
        return 0

    try:
        tasks = pg.pending_tasks(agent="kart", limit=LIMIT)
    except Exception as e:
        print(f"kart_poll: pending_tasks failed ({e}) — skipping", file=sys.stderr)
        return 0

    if not tasks:
        return 0

    print(f"kart_poll: {len(tasks)} pending task(s)", file=sys.stderr)

    for t in tasks:
        task_id = t["id"]
        cmd     = t["task"]
        goal    = t.get("goal")
        started = time.time()

        if goal:
            # Goal-state task: fire a Routine or call LLM to work toward the goal
            status, result = _run_goal_task(pg, task_id, cmd, goal)
        else:
            try:
                proc = subprocess.run(
                    shlex.split(cmd), shell=False, capture_output=True,
                    text=True, timeout=TIMEOUT,
                )
                elapsed = round(time.time() - started, 2)
                status  = "completed" if proc.returncode == 0 else "failed"
                result  = {
                    "returncode": proc.returncode,
                    "stdout":     proc.stdout.strip()[-2000:],
                    "stderr":     proc.stderr.strip()[-500:],
                    "elapsed_s":  elapsed,
                }
            except subprocess.TimeoutExpired:
                status = "failed"
                result = {"error": "timeout", "elapsed_s": TIMEOUT}
            except Exception as e:
                status = "failed"
                result = {"error": str(e)}

        try:
            pg.task_complete(task_id, result, status)
        except Exception as e:
            print(f"kart_poll: task_complete failed for {task_id}: {e}", file=sys.stderr)

        print(f"kart_poll: {task_id} → {status} ({cmd[:60]})", file=sys.stderr)

    pg.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
