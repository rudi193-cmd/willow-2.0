"""
grove_gate.py — Shared Grove health gate for all Willow scripts.
b17: GGATE1  ΔΣ=42

Usage:
    from core.grove_gate import assert_grove, grove_alive

    assert_grove()          # prints banner + sys.exit(1) if Grove is down
    if not grove_alive():   # returns bool, no side effects
        ...
"""
from __future__ import annotations

import os
import sys
import urllib.request

GROVE_HEALTH_URL = os.environ.get("GROVE_HEALTH_URL", "http://localhost:7777/health")

# Fleet runners that must call assert_grove() before doing work (EA422361 P2).
FLEET_GROVE_GATED: tuple[str, ...] = (
    "scripts/kart_poll.py",
    "scripts/grove_msg.py",
    "tools/jukebox.py",
    "tools/nest_watcher.py",
    "willow/grove_listen.py",
    "willow/grove_monitor.py",
    "core/kart_worker.py",
    "agents/hanuman/bin/journal_watcher.py",
    "agents/hanuman/bin/journal_responder.py",
    "agents/hanuman/bin/auto_dream.py",
    "agents/hanuman/bin/dead_reckoning.py",
    "agents/hanuman/bin/kb_truth_drift.py",
    "agents/hanuman/bin/think_map.py",
    "agents/hanuman/bin/upstream_watcher.py",
    "agents/hanuman/bin/upstream_responder.py",
    "agents/hanuman/bin/stabilization_worker.py",
    "agents/hanuman/bin/skill_steward.py",
    "agents/hanuman/bin/kb_briefer.py",
    "agents/hanuman/bin/ratification_triage.py",
    "agents/hanuman/bin/upstream_scout.py",
)

_BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   GROVE IS NOT RUNNING                                           ║
║                                                                  ║
║   {script:<48} requires Grove.  ║
║   Nothing in the fleet executes without it.                      ║
║                                                                  ║
║   Check:  curl http://localhost:7777/health                      ║
║   Start:  ./willow.sh start  (manages grove-serve.service)       ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""


def grove_alive(url: str = GROVE_HEALTH_URL, timeout: int = 3) -> bool:
    """Return True if Grove health endpoint responds 200."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def assert_grove(script: str | None = None, url: str = GROVE_HEALTH_URL) -> None:
    """Print error banner and sys.exit(1) if Grove is not reachable."""
    if grove_alive(url):
        return
    name = script or (sys.argv[0].split("/")[-1] if sys.argv else "this script")
    print(_BANNER.format(script=name[:48]), file=sys.stderr)
    sys.exit(1)
