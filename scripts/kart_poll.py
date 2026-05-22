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
        started = time.time()
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
