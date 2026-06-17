"""Fleet metabolic consecration probe — socket, timer, last briefing."""

from __future__ import annotations

import sqlite3
import subprocess

from willow.fylgja.willow_home import fleet_home, resolve_store_root


def _systemd_user_state(unit: str) -> str:
    """Return active | enabled | installed | missing for a user unit."""
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if proc.returncode == 0 and proc.stdout.strip() == "active":
            return "active"
        proc = subprocess.run(
            ["systemctl", "--user", "is-enabled", unit],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if proc.returncode == 0:
            return "enabled"
        proc = subprocess.run(
            ["systemctl", "--user", "list-unit-files", unit, "--no-legend"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if unit in (proc.stdout or ""):
            return "installed"
    except Exception:
        pass
    return "missing"


def check_metabolic_status() -> dict:
    """Probe metabolic socket, nightly timer, and last briefing record."""
    result: dict = {
        "last_briefing": None,
        "socket": "inactive",
        "timer": "missing",
        "consecrated": False,
    }

    briefings_db = resolve_store_root() / "briefings" / "daily.db"
    if briefings_db.exists():
        try:
            conn = sqlite3.connect(str(briefings_db))
            row = conn.execute(
                "SELECT id, created FROM records ORDER BY created DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if row:
                result["last_briefing"] = row[1]
        except Exception:
            pass

    socket_path = fleet_home() / "metabolic.sock"
    socket_state = _systemd_user_state("willow-metabolic.socket")
    if socket_state == "active" or socket_path.exists():
        result["socket"] = "active"
    elif socket_state in ("enabled", "installed"):
        result["socket"] = "enabled"
    else:
        result["socket"] = "inactive"

    timer_state = _systemd_user_state("willow-metabolic.timer")
    result["timer"] = timer_state

    result["consecrated"] = (
        result["timer"] in ("active", "enabled") and result["last_briefing"] is not None
    )
    return result
