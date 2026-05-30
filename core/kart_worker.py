"""
kart_worker.py — Kart task queue consumer (systemd + optional embedded dashboard)
b17: KRTDSH  ΔΣ=42

Polls public.tasks, claims agent=kart rows, executes via core/kart_execute.py.
Sandbox policy: core/kart_sandbox.py + willow/fylgja/config/kart-sandbox.json
"""
from __future__ import annotations

import importlib
import logging
import sys
import time
from pathlib import Path

logger = logging.getLogger("kart_worker")

_KART_RUN_IDS: dict[str, str] = {}


def _ensure_willow_on_path() -> Path | None:
    from core.kart_sandbox import willow_repo_root

    root = willow_repo_root()
    if root is None:
        return None
    key = str(root)
    if key not in sys.path:
        sys.path.insert(0, key)
    return root


def _kart_run_open(task_id: str, task_text: str, submitted_by: str) -> None:
    if _ensure_willow_on_path() is None:
        logger.debug("run_ledger open skipped: WILLOW_ROOT not found")
        return
    try:
        from core.run_ledger import current_run_id, open_run

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
    """Daemon loop — claim and execute one kart task at a time."""
    from core.kart_execute import execute_task_row, kart_timeout
    from core.pg_bridge import PgBridge

    _self_path = Path(__file__)
    _self_mtime = _self_path.stat().st_mtime

    logger.info("kart daemon started (poll=%ds)", interval)
    pg = None
    while True:
        try:
            _cur_mtime = _self_path.stat().st_mtime
            if _cur_mtime != _self_mtime:
                _self_mtime = _cur_mtime
                _mod = sys.modules.get(__name__)
                if _mod is not None:
                    try:
                        importlib.reload(_mod)
                        logger.info("kart_worker reloaded from disk")
                    except Exception as re:
                        logger.warning("kart_worker reload failed: %s", re)

            if pg is None:
                pg = PgBridge()

            batch = pg.claim_kart_tasks(limit=1)
            if not batch:
                time.sleep(interval)
                continue

            row = batch[0]
            task_id = row["id"]
            task_text = row.get("task") or ""
            submitted_by = row.get("submitted_by") or "?"
            logger.info(
                "kart claimed %s (by %s): %s",
                task_id,
                submitted_by,
                task_text[:60],
            )
            _kart_run_open(task_id, task_text, submitted_by)

            status, result = execute_task_row(
                row, pg, timeout=kart_timeout("daemon"), context="daemon"
            )
            pg.task_complete(task_id, result, status)

            if status == "completed":
                _kart_run_close(task_id, "completed")
                logger.info("kart complete %s", task_id)
            else:
                _kart_run_close(task_id, "crashed")
                logger.warning(
                    "kart failed %s: %s",
                    task_id,
                    result.get("error", result),
                )
        except Exception as e:
            logger.error("kart loop error: %s", e)
            try:
                if pg is not None:
                    pg.close()
            except Exception:
                pass
            pg = None
            time.sleep(interval)
