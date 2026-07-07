#!/usr/bin/env python3
"""
kart_poll.py — drain the pending tasks queue at session close.

Delegates execution to core/kart_execute.py (shell, workflow phases, goal/routine).
Wire as a Stop hook in .claude/settings.json alongside session_close.py.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

LIMIT = int(os.environ.get("KART_POLL_LIMIT", "10"))

# Backward compat for tests that patch workflow helpers on this module.


def main() -> int:
    from core.grove_gate import assert_grove

    assert_grove("kart_poll")

    try:
        from core.kart_execute import drain_claimed_tasks
        from core.pg_bridge import PgBridge

        pg = PgBridge()
    except Exception as e:
        print(f"kart_poll: no Postgres ({e}) — skipping", file=sys.stderr)
        return 0

    try:
        tasks = pg.claim_kart_tasks(limit=LIMIT, lane="fast")
    except Exception as e:
        print(f"kart_poll: claim failed ({e}) — skipping", file=sys.stderr)
        return 0

    if not tasks:
        return 0

    print(f"kart_poll: {len(tasks)} pending task(s)", file=sys.stderr)
    drain_claimed_tasks(pg, tasks, context="poll", log_prefix="kart_poll")
    pg.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
