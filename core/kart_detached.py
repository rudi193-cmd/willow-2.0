"""Detached Kart execution lane — long jobs that outlive the daemon's timeout.

The kart daemon kills every task it runs at ``KART_DAEMON_TIMEOUT`` (default
1800s / 30 min, see ``core/kart_execute.kart_timeout``) and the reaper marks
orphaned ``running`` rows failed at ``KART_STALE_SECONDS`` (default 3600s). That
is the right policy for ordinary shell work — a hung task should die fast — but
it makes the plane unusable for *genuinely* long jobs (benchmark sweeps, full
LoCoMo QA runs, large migrations), which get SIGKILLed mid-flight with their
partial output lost.

This module is the escape hatch. ``launch_detached`` starts the prepared command
in a **new session** (``start_new_session=True`` — the same idiom used by
``sap/openclaw_mcp.py`` and ``scripts/willow_watchdog.py``) so it survives MCP /
daemon restarts, with **no timeout**, streaming stdout+stderr to a persistent log
and writing an exit-status file when it finishes. Nothing reaps it; state is read
back from the files by ``detached_status``.

Sandbox model: the *supervisor* runs on the host (trusted, like the MCP server
itself) so it can write the log + status under ``~/.willow`` — paths a bwrap
sandbox does not bind. The actual *workload* still runs inside bwrap (via
``build_bwrap_argv``) when the sandbox is enabled, so isolation is unchanged.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def detached_root() -> Path:
    """Registry dir for detached jobs: ``$WILLOW_HOME/kart-detached`` (~/.willow)."""
    try:
        from willow.fylgja.willow_home import willow_home

        base = Path(willow_home())
    except Exception:
        base = Path(os.environ.get("WILLOW_HOME", os.path.expanduser("~/.willow")))
    d = base / "kart-detached"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _job_dir(task_id: str) -> Path:
    d = detached_root() / task_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_task_id() -> str:
    """8-hex-upper id, matching the Kart task-id surface."""
    import uuid

    return uuid.uuid4().hex[:8].upper()


# The supervisor is written as a self-contained script (no import-path
# dependency) so it runs even after the parent MCP process is gone. It runs the
# workload argv with no timeout, tees to the log, and atomically writes status.
_SUPERVISOR = r'''
import json, os, subprocess, sys, time

cfg = json.loads(open(sys.argv[1]).read())
argv = cfg["argv"]
env = cfg.get("env") or None
cwd = cfg.get("cwd") or None
log = cfg["log"]
status = cfg["status"]

t0 = time.time()
rc = -1
with open(log, "wb", buffering=0) as lf:
    try:
        p = subprocess.run(
            argv, stdout=lf, stderr=lf, stdin=subprocess.DEVNULL, env=env, cwd=cwd
        )
        rc = p.returncode
    except Exception as e:
        try:
            lf.write(("\n[supervisor error] %r\n" % (e,)).encode())
        except Exception:
            pass
        rc = -1

tmp = status + ".tmp"
with open(tmp, "w") as sf:
    sf.write(json.dumps({"rc": rc, "started": t0, "ended": time.time()}))
os.replace(tmp, status)
'''


def launch_detached(
    cmd: str,
    *,
    task_id: str | None = None,
    allow_net: bool = False,
    cwd: str | None = None,
) -> dict:
    """Launch ``cmd`` (a full bash command string) as a detached, un-timed-out job.

    Returns a handle dict: ``{task_id, pid, log, status_file, state, detached}``.
    Poll progress with :func:`detached_status`.
    """
    from core.kart_sandbox import (
        _sandbox_bash,
        build_bwrap_argv,
        kart_env,
        use_bwrap,
        willow_repo_root,
    )

    task_id = task_id or new_task_id()
    d = _job_dir(task_id)
    log = d / "log"
    status = d / "status"
    cfg_path = d / "supervise.json"
    sup_path = d / "supervise.py"

    bash = _sandbox_bash()
    run_env = kart_env(allow_net=allow_net)
    repo = str(willow_repo_root() or Path.cwd())
    job_cwd = cwd or repo

    if use_bwrap():
        argv = build_bwrap_argv(allow_net=allow_net) + ["--", bash, "-c", cmd]
        sandbox = "bwrap"
    else:
        argv = [bash, "-c", cmd]
        sandbox = "plain"

    cfg_path.write_text(
        json.dumps(
            {
                "argv": argv,
                "env": run_env,
                "cwd": job_cwd,
                "log": str(log),
                "status": str(status),
            }
        )
    )
    sup_path.write_text(_SUPERVISOR)

    py = os.environ.get("WILLOW_PYTHON") or sys.executable or "python3"
    proc = subprocess.Popen(
        [py, str(sup_path), str(cfg_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=repo,
    )

    (d / "meta.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "supervisor_pid": proc.pid,
                "started": time.time(),
                "allow_net": allow_net,
                "sandbox": sandbox,
                "cwd": job_cwd,
                "cmd": cmd[:1000],
            }
        )
    )

    return {
        "task_id": task_id,
        "pid": proc.pid,
        "log": str(log),
        "status_file": str(status),
        "sandbox": sandbox,
        "detached": True,
        "state": "running",
    }


def is_detached(task_id: str) -> bool:
    return (detached_root() / task_id / "meta.json").exists()


def detached_status(task_id: str, *, tail: int = 4000) -> dict | None:
    """Read current state of a detached job from its files. None if unknown id."""
    d = detached_root() / task_id
    if not (d / "meta.json").exists():
        return None
    try:
        meta = json.loads((d / "meta.json").read_text())
    except Exception:
        meta = {}

    log_f = d / "log"
    status_f = d / "status"
    out: dict = {
        "task_id": task_id,
        "detached": True,
        "supervisor_pid": meta.get("supervisor_pid"),
        "sandbox": meta.get("sandbox"),
        "started": meta.get("started"),
    }

    log_tail = ""
    if log_f.exists():
        data = log_f.read_bytes()
        out["log_bytes"] = len(data)
        log_tail = data[-tail:].decode("utf-8", "replace")

    if status_f.exists():
        try:
            st = json.loads(status_f.read_text())
        except Exception:
            st = {}
        rc = st.get("rc")
        out["state"] = "completed" if rc == 0 else "failed"
        out["returncode"] = rc
        if st.get("started") and st.get("ended"):
            out["elapsed_s"] = round(st["ended"] - st["started"], 2)
    else:
        pid = meta.get("supervisor_pid")
        alive = False
        if pid:
            try:
                os.kill(int(pid), 0)
                alive = True
            except (ProcessLookupError, ValueError):
                alive = False
            except PermissionError:
                alive = True
        # Supervisor gone but no status file => it died before writing one.
        out["state"] = "running" if alive else "died"

    out["log_tail"] = log_tail
    return out


def list_detached(limit: int = 50) -> list[dict]:
    """Recent detached jobs, newest first (by meta mtime)."""
    root = detached_root()
    jobs = []
    for meta in root.glob("*/meta.json"):
        try:
            jobs.append((meta.stat().st_mtime, meta.parent.name))
        except OSError:
            continue
    jobs.sort(reverse=True)
    out = []
    for _, tid in jobs[:limit]:
        st = detached_status(tid, tail=0)
        if st:
            st.pop("log_tail", None)
            out.append(st)
    return out
