"""
kart_worker.py — Kart task queue consumer for willow-dashboard
b17: KRTDSH  ΔΣ=42

Ported from willow-1.7/kart_worker.py. Runs as a daemon thread inside
the dashboard process — no separate SAP gate check needed since the dashboard
is already an authorized context.

Polls public.tasks every 5s, claims and executes pending tasks via bwrap sandbox.
Sandbox policy: core/kart_sandbox.py + willow/fylgja/config/kart-sandbox.json
"""
import json
import logging
import os
import re
import resource as _resource
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from core.kart_sandbox import (
    bwrap_available,
    build_bwrap_argv,
    kart_env,
    task_allows_network,
    willow_repo_root,
)

logger = logging.getLogger("kart_worker")

_ALLOW_NET_DIRECTIVE = "# allow_net"

_SHELL_STARTERS = (
    # file ops
    'cp ', 'mv ', 'rm ', 'mkdir ', 'ln ', 'chmod ', 'chown ', 'rsync ',
    'ls ', 'find ', 'fd ', 'tree ',
    # text processing
    'cat ', 'head ', 'tail ', 'grep ', 'rg ', 'sed ', 'awk ',
    'sort ', 'uniq ', 'wc ', 'cut ', 'tr ', 'tee ', 'xargs ',
    'diff ', 'patch ', 'echo ', 'printf ', 'jq ', 'yq ',
    # archive / transfer
    'tar ', 'zip ', 'unzip ', 'gzip ', 'gunzip ', 'bzip2 ', 'xz ',
    'curl ', 'wget ', 'scp ', 'rsync ', 'ssh ',
    # shell / scripting
    'bash ', 'sh ', 'env ', 'which ', 'file ', 'date ', 'bc ',
    'expr ', 'timeout ', 'watch ', 'sleep ',
    # python
    'python3 ', 'python ', 'pip3 ', 'pip ', 'uv ', 'pytest ',
    'black ', 'ruff ', 'mypy ', 'isort ', 'pre-commit ',
    # js / node
    'node ', 'npm ', 'npx ', 'yarn ', 'pnpm ',
    # build tools
    'make ', 'cmake ', 'cargo ', 'go ', 'java ', 'javac ', 'mvn ', 'gradle ',
    # git / gh
    'git ', 'gh ',
    # data / ml
    'ollama ', 'jupyter ', 'kaggle ',
    # crypto / checksum
    'md5sum ', 'sha256sum ', 'sha1sum ', 'base64 ', 'openssl ', 'gpg ',
    # process / system
    'ps ', 'kill ', 'pkill ', 'pgrep ', 'lsof ', 'nohup ', 'strace ',
    # network diagnostics
    'ping ', 'dig ', 'nslookup ', 'nc ', 'netcat ', 'curl ',
    # media / docs
    'ffmpeg ', 'convert ', 'pandoc ',
    # misc utilities
    'fzf ', 'bat ', 'redis-cli ',
    # absolute paths
    str(Path.home()) + os.sep,
    '/usr/', '/opt/', '/tmp/',
    # psql and sqlite3 are intentionally absent — DB access via MCP only
)


def _resource_limits():
    _resource.setrlimit(_resource.RLIMIT_CPU, (1800, 1800))
    _resource.setrlimit(_resource.RLIMIT_AS,  (8 * 1024 ** 3, 8 * 1024 ** 3))
    _resource.setrlimit(_resource.RLIMIT_NOFILE, (1024, 1024))


def _spawn(cmd_type: str, cmd: str, env: dict, allow_net: bool = False) -> subprocess.Popen:
    prefix = build_bwrap_argv(allow_net=allow_net)
    if cmd_type == "python":
        proc = subprocess.Popen(
            prefix + ["python3", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env, preexec_fn=_resource_limits,
        )
        proc.stdin.write(cmd)
        proc.stdin.close()
    elif cmd_type == "script":
        proc = subprocess.Popen(
            prefix + ["bash", "-s"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env, preexec_fn=_resource_limits,
        )
        proc.stdin.write(cmd)
        proc.stdin.close()
    else:
        proc = subprocess.Popen(
            prefix + ["bash", "-c", cmd],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env, preexec_fn=_resource_limits,
        )
    return proc


_SHELL_METACHAR_RE = re.compile(r'[;&|$()\\`><]')


def _validate_shell_cmd(cmd: str) -> bool:
    if _SHELL_METACHAR_RE.search(cmd):
        return False
    cmd_lower = cmd.strip().lower()
    return any(cmd_lower.startswith(s) for s in _SHELL_STARTERS)


def execute_task(task_text: str) -> dict:
    # Self-reload: if the file changed since last import, reload the module and
    # delegate to the fresh execute_task. This lets even the old running daemon
    # pick up code edits without an MCP/process restart.
    import importlib as _il
    import sys as _sys
    _mod = _sys.modules.get(__name__)
    if _mod is not None:
        _cur_mt = Path(__file__).stat().st_mtime
        _last_mt = getattr(_mod, '_kart_exe_mtime', None)
        if _last_mt is None:
            _mod._kart_exe_mtime = _cur_mt
        elif _cur_mt != _last_mt:
            try:
                _il.reload(_mod)
                _mod._kart_exe_mtime = _cur_mt
                logger.info("kart_worker reloaded from execute_task")
                return _mod.execute_task(task_text)
            except Exception as _re:
                logger.warning("kart_worker reload failed: %s", _re)

    outputs = []
    step = 0
    errors = []
    commands = []

    for lang, block in re.findall(r'```(bash|sh|python3?|python)?\n?(.*?)```', task_text, re.DOTALL):
        block = block.strip()
        if not block:
            continue
        is_python = lang in ("python", "python3")
        real_lines = [l for l in block.splitlines() if l.strip() and not l.strip().startswith('#')]
        if is_python:
            commands.append(('python', block))
        elif len(real_lines) == 1:
            commands.append(('shell', real_lines[0]))
        else:
            commands.append(('script', block))

    if not commands:
        for m in re.finditer(r'\(\d+\)\s+(.+?)(?=\s*\(\d+\)|$)', task_text, re.DOTALL):
            fragment = m.group(1).strip().rstrip('.')
            lower = fragment.lower()
            for starter in _SHELL_STARTERS:
                idx = lower.find(starter)
                if idx != -1:
                    cmd = fragment[idx:].split('. ')[0].strip()
                    if cmd not in [c[1] for c in commands]:
                        commands.append(('shell', cmd))
                    break

        for m in re.finditer(
            r'^\s*((?:cp|rsync|python3?|mkdir|chmod|find|grep|curl|mv|rm|git|ollama)\s+.+)$',
            task_text, re.MULTILINE
        ):
            cmd = m.group(1).strip()
            if cmd not in [c[1] for c in commands]:
                commands.append(('shell', cmd))

        if not commands:
            for starter in _SHELL_STARTERS:
                pos = 0
                lower = task_text.lower()
                while True:
                    idx = lower.find(starter, pos)
                    if idx == -1:
                        break
                    end = task_text.find('. ', idx)
                    cmd = task_text[idx:end if end != -1 else len(task_text)].strip().rstrip('.')
                    if cmd and cmd not in [c[1] for c in commands]:
                        commands.append(('shell', cmd))
                    pos = idx + len(starter)

    if not commands:
        return {"success": False, "error": "no executable commands found", "steps": 0}

    if not bwrap_available() and os.environ.get("WILLOW_KART_NO_BWRAP", "").strip().lower() not in ("1", "true", "yes"):
        return {"success": False, "error": "bwrap not found — install bubblewrap", "steps": 0}

    allow_net = task_allows_network(task_text)
    env = kart_env()

    for cmd_type, cmd in commands:
        step += 1
        label = cmd.splitlines()[0][:80] if cmd_type == 'script' else cmd
        try:
            proc = _spawn(cmd_type, cmd, env, allow_net=allow_net)

            stdout_lines = []
            stderr_lines = []

            def _read_stderr(p, buf):
                for line in p.stderr:
                    buf.append(line.rstrip())

            t = threading.Thread(target=_read_stderr, args=(proc, stderr_lines), daemon=True)
            t.start()

            deadline = time.monotonic() + 1800
            for line in proc.stdout:
                line = line.rstrip()
                stdout_lines.append(line)
                if time.monotonic() > deadline:
                    proc.kill()
                    errors.append(f"{label} → timeout")
                    break

            proc.wait()
            t.join(timeout=5)

            output = "\n".join(stdout_lines).strip()
            err = "\n".join(stderr_lines).strip()
            outputs.append(f"$ {label}\n{output}" + (f"\nSTDERR: {err}" if err else ""))
            if proc.returncode not in (0, -9):
                errors.append(f"{label} → exit {proc.returncode}: {err}")
        except Exception as e:
            errors.append(f"{label} → {e}")

    if errors:
        return {"success": False, "error": "; ".join(errors), "output": "\n\n".join(outputs), "steps": step}
    return {"success": True, "response": "\n\n".join(outputs), "steps": step, "provider": "shell"}


def _pg_connect():
    # Intentional dedicated connection — holds across claim+complete atomic pairs; reconnects on error.
    import psycopg2
    dsn = os.environ.get("WILLOW_DB_URL", "")
    if dsn:
        return psycopg2.connect(dsn)
    return psycopg2.connect(
        dbname=os.environ.get("WILLOW_PG_DB", "willow_20"),
        user=os.environ.get("WILLOW_PG_USER", os.environ.get("USER", "")),
    )


def _claim_task(conn) -> dict | None:
    cur = conn.cursor()
    cur.execute("""
        UPDATE public.tasks
        SET status = 'running', updated_at = NOW()
        WHERE id = (
            SELECT id FROM public.tasks
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, task, submitted_by
    """)
    row = cur.fetchone()
    conn.commit()
    cur.close()
    if not row:
        return None
    return {"task_id": row[0], "task": row[1], "submitted_by": row[2]}


def _complete_task(conn, task_id: str, result: dict, steps: int = 0) -> None:
    cur = conn.cursor()
    cur.execute("""
        UPDATE public.tasks
        SET status = 'complete', result = %s, updated_at = NOW()
        WHERE id = %s
    """, (json.dumps(result), task_id))
    conn.commit()
    cur.close()


def _willow_repo_root() -> Path | None:
    return willow_repo_root()


def _ensure_willow_on_path() -> Path | None:
    root = _willow_repo_root()
    if root is None:
        return None
    key = str(root)
    if key not in sys.path:
        sys.path.insert(0, key)
    return root


def _fail_task(conn, task_id: str, error: str) -> None:
    cur = conn.cursor()
    cur.execute("""
        UPDATE public.tasks
        SET status = 'failed', result = %s, updated_at = NOW()
        WHERE id = %s
    """, (json.dumps({"error": error}), task_id))
    conn.commit()
    cur.close()


# Kart child run IDs — keyed by task_id. Never written to the shared /tmp run file
# so kart tasks cannot clobber the parent session's current_run_id pointer.
_KART_RUN_IDS: dict[str, str] = {}


def _kart_run_open(task_id: str, task_text: str, submitted_by: str) -> None:
    """Open a child Run Ledger record for this Kart task. Best-effort.

    Uses write_tmp=False so the parent session's /tmp/willow-run-{AGENT}.json
    is never overwritten by a Kart child run.
    """
    if _ensure_willow_on_path() is None:
        logger.debug("run_ledger open skipped: WILLOW_ROOT not found")
        return
    try:
        from core.run_ledger import open_run, current_run_id

        parent = current_run_id()
        run_id = open_run(
            purpose=f"kart:{task_id[:8]} {task_text[:60]}",
            parent_run_id=parent,
            write_tmp=False,
        )
        if run_id:
            _KART_RUN_IDS[task_id] = run_id
    except Exception as e:
        logger.debug("run_ledger open skipped: %s", e)


def _kart_run_close(task_id: str, status: str) -> None:
    """Close the child run opened for this Kart task. Best-effort.

    Closes directly via DB using the stored run_id — never calls close_run()
    which would clear the parent session's tmp file.
    """
    run_id = _KART_RUN_IDS.pop(task_id, None)
    if not run_id or _ensure_willow_on_path() is None:
        return
    try:
        from core.run_ledger import _connect
        conn = _connect()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "UPDATE willow.runs SET status=%s, ended_at=now() WHERE id=%s AND status='running'",
            (status, run_id),
        )
        conn.close()
    except Exception as e:
        logger.debug("run_ledger close skipped: %s", e)


def kart_loop(interval: int = 5) -> None:
    """Daemon loop — claim and execute one task at a time, poll every interval seconds."""
    import importlib
    import sys as _sys
    _self_path = Path(__file__)
    _self_mtime = _self_path.stat().st_mtime

    logger.info("kart daemon started (dashboard-integrated, poll=%ds)", interval)
    conn = None
    while True:
        try:
            # Hot-reload self if the file changed — picks up edits without MCP restart.
            _cur_mtime = _self_path.stat().st_mtime
            if _cur_mtime != _self_mtime:
                _self_mtime = _cur_mtime
                _mod = _sys.modules.get(__name__)
                if _mod is not None:
                    try:
                        importlib.reload(_mod)
                        logger.info("kart_worker reloaded from disk")
                    except Exception as _re:
                        logger.warning("kart_worker reload failed: %s", _re)

            if conn is None:
                conn = _pg_connect()
            task = _claim_task(conn)
            if not task:
                time.sleep(interval)
                continue
            task_id = task["task_id"]
            task_text = task["task"]
            logger.info("kart claimed %s (by %s): %s", task_id, task.get("submitted_by", "?"), task_text[:60])
            _kart_run_open(task_id, task_text, task.get("submitted_by", ""))
            result = execute_task(task_text)
            if result.get("success"):
                _complete_task(conn, task_id, result, steps=result.get("steps", 0))
                _kart_run_close(task_id, "completed")
                logger.info("kart complete %s (%d steps)", task_id, result.get("steps", 0))
            else:
                _fail_task(conn, task_id, result.get("error", "unknown"))
                _kart_run_close(task_id, "crashed")
                logger.warning("kart failed %s: %s", task_id, result.get("error", "?"))
        except Exception as e:
            logger.error("kart loop error: %s", e)
            try:
                conn.close()
            except Exception:
                pass
            conn = None
            time.sleep(interval)
