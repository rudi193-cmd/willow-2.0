#!/usr/bin/env python3
"""
seed-windows.py — Willow 2.0 Windows seed (replaces seed.py on Windows)

Does everything seed.py does except the curses TUI and Linux-only steps:
  - Verify / create willow_20 database
  - Run schema migrations
  - Start ollama serve, pull required models
  - Seed KB atoms
  - Write seed-boot.json
  - Add willow.py to user PATH

Usage:
    python seed-windows.py
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

WILLOW_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(WILLOW_ROOT))

from willow.fylgja.willow_home import willow_home


def _fleet_home() -> Path:
    return willow_home(WILLOW_ROOT)


WILLOW_HOME = _fleet_home()
BOOT_CONFIG = WILLOW_HOME / "seed-boot.json"


def ok(msg: str)   -> None: print(f"  [ok] {msg}")
def warn(msg: str) -> None: print(f"  [!!] {msg}")
def fail(msg: str) -> None: print(f"  [xx] {msg}"); sys.exit(1)
def hdr(msg: str)  -> None: print(f"\n--- {msg} ---")


# ── Config ────────────────────────────────────────────────────────────────────

def _load_cfg() -> dict:
    try:
        return json.loads(BOOT_CONFIG.read_text()) if BOOT_CONFIG.exists() else {}
    except Exception:
        return {}


def _save_cfg(cfg: dict) -> None:
    WILLOW_HOME.mkdir(parents=True, exist_ok=True)
    BOOT_CONFIG.write_text(json.dumps(cfg, indent=2))


def is_first_run() -> bool:
    return not BOOT_CONFIG.exists()


# ── Postgres ──────────────────────────────────────────────────────────────────

def _pg_env() -> dict:
    return {
        "WILLOW_PG_DB":       os.environ.get("WILLOW_PG_DB", "willow_20"),
        "WILLOW_PG_USER":     os.environ.get("WILLOW_PG_USER", "postgres"),
        "WILLOW_PG_HOST":     os.environ.get("WILLOW_PG_HOST", "localhost"),
        "PGPASSWORD":         os.environ.get("PGPASSWORD", ""),
    }


def _psql(*args: str) -> subprocess.CompletedProcess:
    env = _pg_env()
    cmd = [
        "psql",
        "-U", env["WILLOW_PG_USER"],
        "-h", env["WILLOW_PG_HOST"],
    ] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def _ensure_postgres() -> None:
    hdr("PostgreSQL")
    env = _pg_env()

    # Check connection
    r = _psql("-c", "SELECT 1;", "-d", "postgres")
    if r.returncode != 0:
        fail(
            f"Cannot connect to PostgreSQL as '{env['WILLOW_PG_USER']}' on localhost.\n"
            "  Set PGPASSWORD, WILLOW_PG_USER, or WILLOW_PG_HOST env vars and retry.\n"
            f"  Error: {r.stderr.strip()}"
        )
    ok(f"Connected as {env['WILLOW_PG_USER']}@{env['WILLOW_PG_HOST']}")

    # Create database if missing
    r = _psql("-lqt", "-d", "postgres")
    if env["WILLOW_PG_DB"] not in r.stdout:
        print(f"  Creating database {env['WILLOW_PG_DB']}...")
        r2 = _psql("-c", f"CREATE DATABASE {env['WILLOW_PG_DB']};", "-d", "postgres")
        if r2.returncode != 0:
            fail(f"Could not create database: {r2.stderr.strip()}")
        ok(f"Created {env['WILLOW_PG_DB']}")
    else:
        ok(f"Database {env['WILLOW_PG_DB']} exists")

    # Run migrations
    try:
        from core.pg_bridge import PgBridge, run_migrations
        b = PgBridge()
        run_migrations(b.conn)
        b.conn.commit()
        b.close()
        ok("Migrations complete")
    except Exception as e:
        warn(f"Migration warning (non-fatal): {e}")


# ── Ollama ────────────────────────────────────────────────────────────────────

def _ensure_ollama() -> None:
    hdr("Ollama")

    if not shutil.which("ollama"):
        fail("Ollama not found. Install from https://ollama.com/download and re-run.")

    # Start serve if not running
    r = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    if r.returncode != 0:
        print("  Starting ollama serve...")
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0,
        )
        time.sleep(3)
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if r.returncode != 0:
            warn("ollama serve did not start — inference may not work")
            return

    existing = r.stdout
    ok("ollama serve running")

    if "nomic-embed-text" not in existing:
        print("  Pulling nomic-embed-text (required for KB search)...")
        subprocess.run(["ollama", "pull", "nomic-embed-text"])

    if "llama3.2" not in existing:
        print("  Pulling llama3.2:3b (default inference model)...")
        subprocess.run(["ollama", "pull", "llama3.2:3b"])

    ok("Models ready")


# ── Store / vault dirs ────────────────────────────────────────────────────────

def _ensure_dirs() -> None:
    hdr("Willow home")
    for d in [
        WILLOW_HOME / "store",
        WILLOW_HOME / "vault",
        WILLOW_HOME / "handoffs",
        WILLOW_HOME / "logs",
    ]:
        d.mkdir(parents=True, exist_ok=True)
    ok(f"fleet home layout ready ({WILLOW_HOME})")


# ── KB seed ───────────────────────────────────────────────────────────────────

def _seed_kb() -> None:
    hdr("KB seed")
    try:
        from core.pg_bridge import PgBridge
        from core.seed_kb import seed_kb
        b = PgBridge()
        seed_kb(b, skip_existing=True)
        b.close()
        ok("KB atoms seeded")
    except Exception as e:
        warn(f"KB seed skipped: {e}")


# ── Birth event ───────────────────────────────────────────────────────────────

def _write_birth_event() -> None:
    try:
        from core.pg_bridge import PgBridge
        from core.version import VERSION
        b = PgBridge()
        b.cmb_put("cmb_origin", {
            "event": "system_birth",
            "version": VERSION,
            "platform": "windows",
            "willow_root": str(WILLOW_ROOT),
            "timestamp": datetime.now().isoformat(),
        })
        b.close()
    except Exception:
        pass


# ── PATH ──────────────────────────────────────────────────────────────────────

def _ensure_path() -> None:
    hdr("PATH")
    willow_dir = str(WILLOW_ROOT)
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        )
        try:
            current, _ = winreg.QueryValueEx(key, "PATH")
        except FileNotFoundError:
            current = ""
        if willow_dir.lower() not in current.lower():
            new_path = f"{current};{willow_dir}" if current else willow_dir
            winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
            ok(f"Added {willow_dir} to user PATH (reopen shell to take effect)")
        else:
            ok("willow-2.0 already on PATH")
        winreg.CloseKey(key)
    except Exception as e:
        warn(f"Could not update PATH automatically: {e}")
        warn(f"Add manually: {willow_dir}")


# ── Boot config ───────────────────────────────────────────────────────────────

def _write_boot_config() -> None:
    cfg = _load_cfg()
    if not cfg.get("first_run_at"):
        cfg["first_run_at"] = datetime.now().isoformat()
    cfg["last_boot_at"] = datetime.now().isoformat()
    cfg["platform"] = "windows"
    _save_cfg(cfg)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nWillow 2.0 — Windows seed")
    print("=" * 40)

    _ensure_dirs()
    _ensure_postgres()
    _ensure_ollama()

    if is_first_run():
        _seed_kb()
        _write_birth_event()
        _ensure_path()

    _write_boot_config()

    print("\n" + "=" * 40)
    print("  Willow seed complete.")
    print("  Run: python willow.py status")
    print()


if __name__ == "__main__":
    main()
