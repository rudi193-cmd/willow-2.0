#!/usr/bin/env python3
"""Check SAFE canonical paths vs fleet config. Exit 1 on hard failures."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from willow.fylgja.willow_home import willow_home

HOME = Path.home()
GITHUB = HOME / "github"
CANON = GITHUB / "SAFE"
LINK = HOME / "SAFE"
_FLEET_HOME = willow_home(REPO)

FAIL = 0


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def warn(msg: str) -> None:
    print(f"  WARN {msg}")


def bad(msg: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  FAIL {msg}", file=sys.stderr)


def read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    print("SAFE path audit")
    print(f"  canonical: {CANON}")
    print(f"  legacy:    {LINK}")

    if not CANON.is_dir():
        bad(f"missing canonical dir {CANON}")
    else:
        ok(f"canonical exists ({CANON})")

    if LINK.is_symlink():
        target = LINK.resolve()
        if target == CANON.resolve():
            ok("~/SAFE symlink → ~/github/SAFE")
        else:
            bad(f"~/SAFE symlink → {target} (expected {CANON})")
    elif LINK.is_dir():
        bad("~/SAFE is still a real directory — run scripts/repair_safe_layout.sh")
    elif not LINK.exists():
        warn("~/SAFE missing (create symlink after move)")

    for sub in ("Applications", "Agents"):
        p = CANON / sub
        if p.is_dir():
            n = len(list(p.iterdir())) if p.exists() else 0
            ok(f"{sub}/ present ({n} entries)")
        else:
            bad(f"missing {p}")

    env = read_env_file(_FLEET_HOME / "env")
    for key in ("WILLOW_SAFE_ROOT", "WILLOW_AGENTS_ROOT"):
        val = env.get(key, os.environ.get(key, ""))
        if not val:
            warn(f"{key} not set in $WILLOW_HOME/env")
            continue
        p = Path(val).expanduser()
        if not p.is_dir():
            bad(f"{key}={val} does not exist")
        elif CANON.resolve() not in p.resolve().parents and p.resolve() != CANON.resolve():
            bad(f"{key}={val} outside ~/github/SAFE")
        else:
            ok(f"{key} → {p}")

    settings = _FLEET_HOME / "settings.global.json"
    if settings.is_file():
        data = json.loads(settings.read_text(encoding="utf-8"))
        paths = data.get("paths", {})
        fleet = data.get("fleet", {})
        for key in ("safe_root", "agents_root"):
            val = paths.get(key) or fleet.get(key, "")
            if not val:
                warn(f"settings.global.json paths.{key} empty")
                continue
            p = Path(val)
            if not p.is_dir():
                bad(f"paths.{key}={val} missing")
            else:
                ok(f"paths.{key} → {p}")

    mcp_dir = REPO / "agents"
    if mcp_dir.is_dir():
        for mcp in sorted(mcp_dir.glob("*/config/mcp.json")):
            data = json.loads(mcp.read_text(encoding="utf-8"))
            env = data.get("mcpServers", {}).get("willow", {}).get("env", {})
            for key in ("WILLOW_SAFE_ROOT", "WILLOW_AGENTS_ROOT"):
                val = env.get(key, "")
                if not val:
                    bad(f"{mcp}: missing {key}")
                    continue
                p = Path(val)
                if not p.is_dir():
                    bad(f"{mcp}: {key}={val} missing")
                else:
                    ok(f"{mcp.parent.parent.name} {key} ok")

    repo_mcp = REPO / ".willow" / "mcp.json"
    if repo_mcp.is_file():
        data = json.loads(repo_mcp.read_text(encoding="utf-8"))
        env = data.get("mcpServers", {}).get("willow", {}).get("env", {})
        if "WILLOW_AGENTS_ROOT" not in env:
            warn(f"{repo_mcp}: missing WILLOW_AGENTS_ROOT — run ./willow agents install")
        for key in ("WILLOW_SAFE_ROOT", "WILLOW_AGENTS_ROOT"):
            val = env.get(key, "")
            if val and not Path(val).is_dir():
                bad(f"{repo_mcp}: {key}={val} missing")

    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
