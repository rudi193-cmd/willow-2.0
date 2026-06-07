#!/usr/bin/env python3
"""Cross-platform launcher for Willow 2.0. Equivalent to willow.sh on Windows."""

import os
import socket
import subprocess
import sys
from pathlib import Path

# ── Project root & Python path ────────────────────────────────────────────────
WILLOW_ROOT = Path(__file__).resolve().parent
if str(WILLOW_ROOT) not in sys.path:
    sys.path.insert(0, str(WILLOW_ROOT))

# Replicate platform_compat constants inline to avoid shadowing the willow/
# package with this file (willow.py at the root would be found first as
# "willow" when doing `from willow.platform_compat import ...`).
IS_WINDOWS: bool = sys.platform == "win32"
IS_POSIX: bool = not IS_WINDOWS

# ── Python interpreter (mirrors willow.sh resolution order) ──────────────────
def _find_python() -> str:
    if "WILLOW_PYTHON" in os.environ:
        return os.environ["WILLOW_PYTHON"]
    candidates = [
        WILLOW_ROOT / ".venv-dev" / ("Scripts" if IS_WINDOWS else "bin") / ("python.exe" if IS_WINDOWS else "python3"),
        Path.home() / ".willow-venv" / ("Scripts" if IS_WINDOWS else "bin") / ("python.exe" if IS_WINDOWS else "python3"),
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return sys.executable

WILLOW_PYTHON = _find_python()


def _willow_home_module():
    """Load willow_home without importing the willow package (this file shadows it)."""
    import importlib.util

    path = WILLOW_ROOT / "willow" / "fylgja" / "willow_home.py"
    spec = importlib.util.spec_from_file_location("_willow_home_resolver", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load willow_home from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fleet_home() -> Path:
    return _willow_home_module().willow_home(WILLOW_ROOT)


# ── Environment setup (mirrors willow.sh exports) ────────────────────────────
def _setup_env() -> None:
    wh = _willow_home_module()
    fleet = wh.willow_home(WILLOW_ROOT)
    os.environ.setdefault("WILLOW_ROOT", str(WILLOW_ROOT))
    os.environ.setdefault("WILLOW_HOME", str(fleet))
    os.environ.setdefault("WILLOW_STORE_ROOT", str(wh.resolve_store_root(WILLOW_ROOT)))
    os.environ.setdefault("WILLOW_VAULT", str(fleet / "vault.db"))
    os.environ.setdefault("WILLOW_PG_DB", "willow_20")
    os.environ.setdefault("WILLOW_AGENT_NAME", "hanuman")
    existing = os.environ.get("PYTHONPATH", "")
    if str(WILLOW_ROOT) not in existing.split(os.pathsep):
        os.environ["PYTHONPATH"] = str(WILLOW_ROOT) + (os.pathsep + existing if existing else "")

# ── Helpers ───────────────────────────────────────────────────────────────────
def _run(script: Path, *args: str) -> int:
    """Run a Python script as a subprocess, forwarding remaining argv."""
    cmd = [WILLOW_PYTHON, str(script)] + list(args)
    result = subprocess.run(cmd)
    return result.returncode

def _pg_reachable(host: str = "localhost", port: int = 5432, timeout: float = 2.0) -> bool:
    """Check Postgres availability via a plain TCP socket (no psycopg2 needed)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def _installed_version() -> str:
    version_file = _fleet_home() / "version"
    repo_version_file = WILLOW_ROOT / "VERSION"
    # Sync repo VERSION → $WILLOW_HOME/version (mirrors _willow_sync_version)
    if repo_version_file.exists():
        ver = repo_version_file.read_text().strip()
        if ver:
            version_file.parent.mkdir(parents=True, exist_ok=True)
            version_file.write_text(ver)
    return version_file.read_text().strip() if version_file.exists() else "not installed"

# ── Subcommand handlers ───────────────────────────────────────────────────────
def cmd_help() -> int:
    print("Willow 2.0 — cross-platform launcher")
    print()
    print("Usage: python willow.py <command> [args]")
    print()
    print("Commands:")
    print("  start         Start the SAP MCP server (stdio)")
    print("  stop          Stop background services")
    print("  status        Check Postgres + service health")
    print("  seed          Run seed.py (initial data setup)")
    print("  install       Run root.py (install / configure)")
    print("  root          Alias for install")
    print("  grove         Launch Grove app (app.py)")
    print("  mcp           Start the SAP MCP server (alias for start)")
    print("  help          Show this message")
    return 0

def cmd_start() -> int:
    sap_mcp = WILLOW_ROOT / "sap" / "sap_mcp.py"
    if not sap_mcp.exists():
        print(f"ERROR: {sap_mcp} not found", file=sys.stderr)
        return 1
    return _run(sap_mcp)

def cmd_stop() -> int:
    if IS_POSIX:
        result = subprocess.run(["systemctl", "--user", "stop", "willow-metabolic.socket"],
                                capture_output=True)
        if result.returncode == 0:
            print("  Metabolic socket stopped.")
        else:
            print("  Metabolic socket was not running (or systemctl unavailable).")
    else:
        print("  Windows: close the terminal window running the Willow services.")
    return 0

def cmd_status() -> int:
    print("Willow 2.0 — status")
    print(f"  Root:     {WILLOW_ROOT}")
    print(f"  Store:    {os.environ.get('WILLOW_STORE_ROOT')}")
    print(f"  Vault:    {os.environ.get('WILLOW_VAULT')}")
    print(f"  Version:  {_installed_version()}")
    print(f"  Python:   {WILLOW_PYTHON}")

    # Postgres check — plain socket, no psycopg2 required
    pg_ok = _pg_reachable()
    print(f"  Postgres: {'reachable on localhost:5432' if pg_ok else 'NOT reachable on localhost:5432'}")

    if IS_POSIX:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "willow-metabolic.socket"],
            capture_output=True, text=True
        )
        active = result.stdout.strip() == "active"
        print(f"  Metabolic socket: {'active' if active else 'inactive'}")
    else:
        print("  Metabolic socket: N/A (Windows — run services manually)")
    return 0

def cmd_seed() -> int:
    script = WILLOW_ROOT / "seed.py"
    if not script.exists():
        print(f"ERROR: {script} not found", file=sys.stderr)
        return 1
    return _run(script, *sys.argv[2:])

def cmd_root_install() -> int:
    script = WILLOW_ROOT / "root.py"
    if not script.exists():
        print(f"ERROR: {script} not found", file=sys.stderr)
        return 1
    return _run(script, *sys.argv[2:])

def cmd_grove() -> int:
    script = WILLOW_ROOT / "app.py"
    if not script.exists():
        print(f"ERROR: {script} not found", file=sys.stderr)
        return 1
    return _run(script, *sys.argv[2:])

# ── Dispatch ──────────────────────────────────────────────────────────────────
def main() -> int:
    _setup_env()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    dispatch = {
        "help":    cmd_help,
        "start":   cmd_start,
        "mcp":     cmd_start,
        "stop":    cmd_stop,
        "status":  cmd_status,
        "seed":    cmd_seed,
        "install": cmd_root_install,
        "root":    cmd_root_install,
        "grove":   cmd_grove,
    }
    handler = dispatch.get(cmd)
    if handler is None:
        print(f"Unknown command: {cmd!r}", file=sys.stderr)
        cmd_help()
        return 1
    return handler()

if __name__ == "__main__":
    sys.exit(main())
