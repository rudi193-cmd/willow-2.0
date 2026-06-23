#!/usr/bin/env python3
"""
willow-launcher.py — Public Ready v1 golden path.

  python willow-launcher.py

Starts Docker Postgres, minimal public setup, seeds demo memory, opens browser chat.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
VENV = REPO_ROOT / ".venv-dev"
VENV_PY = VENV / "bin" / "python3"


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _run(cmd: list[str], *, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    merged = {**os.environ, **(env or {})}
    _eprint(f"  → {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=merged,
        check=check,
        text=True,
    )


def _require_docker() -> None:
    if not shutil.which("docker"):
        _eprint("Docker is required for the public demo. Install Docker and retry.")
        sys.exit(1)
    probe = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        _eprint("Docker is installed but not running. Start Docker and retry.")
        sys.exit(1)


def _require_python() -> None:
    if sys.version_info < (3, 11):
        _eprint(f"Python 3.11+ required (found {sys.version_info.major}.{sys.version_info.minor}).")
        sys.exit(1)


def _ensure_venv() -> Path:
    if not VENV_PY.is_file():
        _eprint("Creating .venv-dev …")
        _run([sys.executable, "-m", "venv", str(VENV)])
        _run([str(VENV / "bin" / "pip"), "install", "-q", "-r", "requirements.txt"])
    return VENV_PY


def _launcher_env() -> dict[str, str]:
    from core.public_demo import launcher_env

    env = launcher_env()
    env["WILLOW_ROOT"] = str(REPO_ROOT)
    env["WILLOW_CONFIG_MODE"] = "public-fallback"
    env["WILLOW_HOME"] = str(REPO_ROOT / ".willow" / "generated")
    env["PYTHONPATH"] = str(REPO_ROOT)
    return env


def _start_docker_db(env: dict[str, str]) -> None:
    _eprint("Starting willow-db (Docker) …")
    compose = shutil.which("docker")
    _run([compose, "compose", "up", "-d", "willow-db"], env=env)
    _wait_pg_ready(env, timeout_s=90)


def _wait_pg_ready(env: dict[str, str], *, timeout_s: int) -> None:
    host = env.get("WILLOW_PG_HOST", "127.0.0.1")
    port = env.get("WILLOW_PG_PORT", "5432")
    user = env.get("WILLOW_PG_USER", "willow")
    db = env.get("WILLOW_PG_DB", "willow_20")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        probe = subprocess.run(
            [
                "docker", "compose", "exec", "-T", "willow-db",
                "pg_isready", "-U", user, "-d", db,
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            env={**os.environ, **env},
        )
        if probe.returncode == 0:
            _eprint(f"  ✓ Postgres ready at {host}:{port}/{db}")
            return
        time.sleep(2)
    _eprint("Postgres did not become ready in time.")
    sys.exit(1)


def _link_public_home(py: Path, env: dict[str, str]) -> None:
    _eprint("Linking public-fallback fleet home …")
    _run([str(py), "-m", "willow.fylgja.link_fleet_home", "--public"], env=env)


def _migrate_and_seed(py: Path, env: dict[str, str]) -> None:
    _eprint("Running migrations and seeding demo memory …")
    script = """
from core.pg_bridge import PgBridge, run_migrations
from core.public_demo import seed_demo_atoms, demo_banner

bridge = PgBridge()
try:
    run_migrations(bridge.conn)
    bridge.conn.commit()
    result = seed_demo_atoms(bridge)
    print("  ✓ Demo seed:", result)
    print("  ✓", demo_banner())
finally:
    bridge.close()
"""
    _run([str(py), "-c", script], env=env)


def _open_browser(port: int) -> None:
    url = f"http://127.0.0.1:{port}/"
    _eprint(f"Opening {url}")
    try:
        webbrowser.open(url)
    except Exception:
        _eprint(f"Open manually: {url}")


def main() -> None:
    _require_python()
    _require_docker()

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from core.public_demo import demo_banner

    _eprint("")
    _eprint("━━━ Willow public demo ━━━")
    _eprint(demo_banner())
    _eprint("")

    env = _launcher_env()
    py = _ensure_venv()
    _start_docker_db(env)
    _link_public_home(py, env)
    _migrate_and_seed(py, env)

    port = int(os.environ.get("WILLOW_PUBLIC_PORT", "7777"))
    _open_browser(port)

    _eprint("")
    _eprint("Chat server running — Ctrl+C to stop.")
    _eprint("")

    os.execve(
        str(py),
        [str(py), "-m", "core.public_serve", "--port", str(port)],
        {**os.environ, **env},
    )


if __name__ == "__main__":
    main()
