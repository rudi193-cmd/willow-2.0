"""Server code-version stamp + staleness detection.

The MCP server imports its Python modules once at process start. Code merged to
master afterward does NOT take effect until the process restarts (``fleet_restart``
or any real process exit). ``fleet_reload`` only hot-swaps a small hardcoded
module whitelist (blast, inference, pg_bridge, store, gate, safe_agents) — it does
*not* reload core modules like ``dream_state``/``run_ledger`` or the facade tool
bodies in ``sap_mcp``. Historically nothing warned when the running code drifted
behind ``git HEAD``, so merged fixes silently ran stale (dream_state, SOIL layout,
ledger compaction, …).

This module stamps the commit the process started on (``boot_sha`` — primed once
at server import) and compares it to the working-tree HEAD on demand
(``staleness``). Surface the result in ``fleet_status``/``willow_status`` so a
stale server is visible without anyone having to remember the restart.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(args: list[str]) -> str | None:
    """Run a git command in the repo root. Returns stripped stdout, or None on
    any failure (git missing, not a repo, timeout) — never raises."""
    try:
        r = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


@lru_cache(maxsize=1)
def boot_sha() -> str | None:
    """HEAD at first call, cached for the process lifetime.

    Prime this once early in server startup (import time) so it captures the
    commit the running process actually loaded, before HEAD can advance under it.
    """
    return _git(["rev-parse", "HEAD"])


def current_head() -> str | None:
    """Current working-tree HEAD (uncached). May have advanced past boot_sha()
    if PRs merged after the server started."""
    return _git(["rev-parse", "HEAD"])


def staleness() -> dict:
    """Compare the booted commit to the working-tree HEAD.

    ``commits_behind`` counts commits reachable from HEAD but not from the booted
    SHA — i.e. how many merged commits the running process has not loaded.
    ``stale`` is True whenever the booted SHA differs from HEAD, which means a
    ``fleet_restart`` is needed to activate the on-disk code.
    """
    booted = boot_sha()
    head = current_head()
    info: dict = {
        "booted_sha": booted[:8] if booted else None,
        "head_sha": head[:8] if head else None,
        "commits_behind": 0,
        "stale": False,
    }
    if not booted or not head:
        info["note"] = "git unavailable — staleness unknown"
        return info
    if booted == head:
        return info

    count = _git(["rev-list", "--count", f"{booted}..{head}"])
    try:
        n = int(count) if count is not None else 0
    except ValueError:
        n = 0
    info["commits_behind"] = n
    info["stale"] = True
    info["note"] = (
        f"server running {n} commit(s) behind HEAD — fleet_restart to activate merged code"
        if n > 0
        else "server HEAD differs from checkout — fleet_restart to resync"
    )
    return info
