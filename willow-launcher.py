#!/usr/bin/env python3
"""
willow-launcher.py — Public Ready v1 golden path.

  python willow-launcher.py

Uses existing Postgres when available; otherwise starts Docker willow-db on a free port.
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
        _eprint("Docker is required when no local Postgres is available. Install Docker and retry.")
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


def _ensure_postgres(env: dict[str, str]) -> dict[str, str]:
    from core.public_launcher_pg import postgres_endpoint_label, resolve_postgres_plan

    plan = resolve_postgres_plan(env)
    resolved = plan["env"]
    if plan["mode"] == "existing":
        _eprint(f"Using existing Postgres at {postgres_endpoint_label(resolved)}")
        return resolved

    _require_docker()
    publish = plan["publish_port"]
    if publish != 5432:
        _eprint(f"Port 5432 is in use — publishing Docker Postgres on host port {publish}")
    _eprint("Starting willow-db (Docker) …")
    compose = shutil.which("docker")
    _run([compose, "compose", "up", "-d", "willow-db"], env=resolved)
    _wait_pg_ready(resolved, timeout_s=90)
    return resolved


def _wait_pg_ready(env: dict[str, str], *, timeout_s: int) -> None:
    from core.public_launcher_pg import postgres_endpoint_label, try_pg_connect

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if try_pg_connect(env):
            _eprint(f"  ✓ Postgres ready at {postgres_endpoint_label(env)}")
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


def _resolve_chat_port(env: dict[str, str]) -> int:
    from core.public_serve import DEFAULT_PUBLIC_PORT, pick_public_chat_port

    explicit = "WILLOW_PUBLIC_PORT" in os.environ
    preferred = int(os.environ.get("WILLOW_PUBLIC_PORT", str(DEFAULT_PUBLIC_PORT)))
    try:
        port, skipped = pick_public_chat_port(preferred=preferred, explicit=explicit)
    except OSError as exc:
        _eprint(str(exc))
        _eprint("Stop the other listener or set WILLOW_PUBLIC_PORT to a free port.")
        sys.exit(1)
    if skipped is not None:
        _eprint(f"Port {skipped} is in use — chat server on {port}")
    env["WILLOW_PUBLIC_PORT"] = str(port)
    return port


def main() -> None:
    _require_python()

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from core.public_demo import demo_banner

    _eprint("")
    _eprint("━━━ Willow public demo ━━━")
    _eprint(demo_banner())
    _eprint("")

    env = _launcher_env()
    py = _ensure_venv()
    env = _ensure_postgres(env)
    _link_public_home(py, env)
    _migrate_and_seed(py, env)

    port = _resolve_chat_port(env)
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
