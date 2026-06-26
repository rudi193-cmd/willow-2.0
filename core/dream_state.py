"""Shared AutoDream condition checks (SOIL state + willow.runs session count)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from core.lock_ttl import lock_is_live


def dream_conditions(
    app_id: str,
    store,
    pg=None,
) -> dict[str, Any]:
    """Return whether AutoDream should run for *app_id*.

    Gates: 24h+ since last dream AND 5+ willow.runs sessions since last dream.
    A stale lock (crashed run, older than the TTL) is ignored so the routine
    self-heals rather than blocking forever.
    """
    dream_state = store.get(f"{app_id}/dream", "state") or {}
    if lock_is_live(dream_state):
        return {
            "should_dream": False,
            "locked": True,
            "reason": "dream already running",
        }

    now = datetime.now(timezone.utc)
    last_str = dream_state.get("last_dream_at", "")
    hours_elapsed = 999.0
    if last_str:
        try:
            last = datetime.fromisoformat(last_str)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            hours_elapsed = (now - last).total_seconds() / 3600
        except Exception:
            pass

    sessions_since = 0
    if pg is not None:
        try:
            pg._ensure_conn()
            with pg.conn.cursor() as cur:
                # Count real sessions only. Kart shell tasks also open willow.runs
                # rows (purpose='kart:...', one per task) and currently land with a
                # NULL parent_run_id because the kart-worker daemon cannot see the
                # session's run file — so they masquerade as top-level sessions and
                # inflate this count ~16x. Exclude them so the dream gate counts
                # boots, not shell commands. See flag dream-kart-runs-pollution.
                if last_str:
                    cur.execute(
                        "SELECT COUNT(*) FROM willow.runs "
                        "WHERE initiator=%s AND started_at > %s "
                        "AND (purpose IS NULL OR purpose NOT LIKE 'kart:%%')",
                        (app_id, last_str),
                    )
                else:
                    cur.execute(
                        "SELECT COUNT(*) FROM willow.runs "
                        "WHERE initiator=%s "
                        "AND (purpose IS NULL OR purpose NOT LIKE 'kart:%%')",
                        (app_id,),
                    )
                row = cur.fetchone()
                sessions_since = row[0] if row else 0
        except Exception:
            sessions_since = dream_state.get("sessions_since_dream", 0)

    should_dream = hours_elapsed >= 24 and sessions_since >= 5
    return {
        "should_dream": should_dream,
        "hours_since_dream": round(hours_elapsed, 1),
        "sessions_since_dream": sessions_since,
        "last_dream_at": last_str or None,
        "reason": (
            f"{hours_elapsed:.1f}h elapsed, {sessions_since} sessions since last dream"
            if should_dream
            else f"conditions not met: {hours_elapsed:.1f}h / 24h, {sessions_since} / 5 sessions"
        ),
    }


def queue_dream_task(pg, app_id: str, submitted_by: str = "willow", force: bool = False) -> Optional[str]:
    """Queue agents/{app}/bin/auto_dream.py via Kart. Returns task_id or None."""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    script = root / "agents" / app_id / "bin" / "auto_dream.py"
    if not script.is_file():
        script = root / "agents" / "hanuman" / "bin" / "auto_dream.py"
    cmd_parts = [sys.executable, str(script), "run", f"--app-id={app_id}"]
    if force:
        cmd_parts.append("--force")
    cmd = " ".join(cmd_parts) + "\n# allow_localhost"
    return pg.submit_task(cmd, submitted_by=submitted_by, agent="kart")
