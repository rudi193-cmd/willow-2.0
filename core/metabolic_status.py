"""Fleet metabolic consecration probe — socket, timer, last briefing."""

from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

from willow.fylgja.willow_home import metabolic_fleet_home


def _systemd_user_env() -> dict[str, str]:
    """Best-effort user-session env for MCP/daemon contexts missing login session."""
    env = os.environ.copy()
    if "XDG_RUNTIME_DIR" not in env:
        try:
            env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
        except Exception:
            pass
    if "DBUS_SESSION_BUS_ADDRESS" not in env:
        runtime = env.get("XDG_RUNTIME_DIR", "")
        if runtime:
            bus = Path(runtime) / "bus"
            if bus.is_socket():
                env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus}"
    return env


def _systemd_user_state(unit: str) -> str:
    """Return active | enabled | installed | missing for a user unit."""
    env = _systemd_user_env()
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True,
            text=True,
            timeout=3,
            env=env,
        )
        state = (proc.stdout or "").strip()
        if proc.returncode == 0 and state in ("active", "waiting"):
            return "active"
        proc = subprocess.run(
            ["systemctl", "--user", "is-enabled", unit],
            capture_output=True,
            text=True,
            timeout=3,
            env=env,
        )
        if proc.returncode == 0:
            return "enabled"
        proc = subprocess.run(
            ["systemctl", "--user", "list-unit-files", unit, "--no-legend"],
            capture_output=True,
            text=True,
            timeout=3,
            env=env,
        )
        if unit in (proc.stdout or ""):
            return "installed"
        unit_file = Path.home() / ".config/systemd/user" / unit
        if unit_file.is_file():
            return "installed"
    except Exception:
        pass
    return "missing"


def restart_user_systemd_units(
    units: tuple[str, ...],
    *,
    action: str = "restart",
) -> dict:
    """Restart user systemd units from the MCP host process (not Kart bwrap)."""
    import shutil

    if not shutil.which("systemctl"):
        return {"status": "unavailable", "reason": "systemctl not found"}
    env = _systemd_user_env()
    restarted: list[str] = []
    skipped: list[dict] = []
    errors: list[dict] = []
    for unit in units:
        try:
            proc = subprocess.run(
                ["systemctl", "--user", action, unit],
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
            )
            if proc.returncode == 0:
                restarted.append(unit)
                continue
            err = (proc.stderr or proc.stdout or "").strip()[:300]
            low = err.lower()
            if any(
                token in low
                for token in ("not found", "not loaded", "does not exist", "no such file")
            ):
                skipped.append({"unit": unit, "reason": err})
            else:
                errors.append(
                    {"unit": unit, "returncode": proc.returncode, "stderr": err}
                )
        except Exception as exc:
            errors.append({"unit": unit, "error": str(exc)})
    if errors and not restarted:
        status = "error"
    elif errors or skipped:
        status = "partial"
    elif restarted:
        status = "restarted"
    else:
        status = "skipped"
    return {
        "status": status,
        "units": restarted,
        "skipped": skipped or None,
        "errors": errors or None,
    }


def check_metabolic_status() -> dict:
    """Probe metabolic socket, nightly timer, and last briefing record."""
    result: dict = {
        "last_briefing": None,
        "socket": "inactive",
        "timer": "missing",
        "consecrated": False,
    }

    # Fleet-global artifacts: use metabolic_fleet_home() so a repo-local
    # WILLOW_HOME override (public-fallback MCP) does not hide briefings.
    home = metabolic_fleet_home()
    briefings_db = home / "store" / "briefings" / "daily.db"
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

    socket_path = home / "metabolic.sock"
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
