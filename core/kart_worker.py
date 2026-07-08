"""
kart_worker.py — Kart task queue consumer (systemd + optional embedded dashboard)
b17: KRTDSH  ΔΣ=42

Polls public.tasks, claims agent=kart rows, executes via core/kart_execute.py.
Sandbox policy: core/kart_sandbox.py + willow/fylgja/config/kart-sandbox.json

Lane workers (set via KART_WORKER_LANE):
  fast  — kart-worker.service; N concurrent slots (KART_FAST_WORKERS, default 3)
  batch — kart-worker-batch.service; one long job at a time
  all   — legacy single-threaded fast-then-batch (deprecated)
"""
from __future__ import annotations

import importlib
import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

logger = logging.getLogger("kart_worker")

_KART_RUN_IDS: dict[str, str] = {}


def _watchmen_key_for_mode(mode: str) -> str:
    from core.kart_lanes import KART_WORKER_MODE_BATCH

    return "kart_worker_batch" if mode == KART_WORKER_MODE_BATCH else "kart_worker"


def _maybe_write_heartbeat(tick_ok: bool = True, **extra) -> None:
    """Throttled SOIL heartbeat for fleet_status watchmen (loops.json interval_sec)."""
    from core.kart_lanes import worker_mode
    from core.loop_heartbeat import write_throttled

    write_throttled(_watchmen_key_for_mode(worker_mode()), tick_ok=tick_ok, **extra)


def _ensure_willow_on_path() -> Path | None:
    from core.kart_sandbox import willow_repo_root

    root = willow_repo_root()
    if root is None:
        return None
    key = str(root)
    if key not in sys.path:
        sys.path.insert(0, key)
    return root


def _kart_run_open(task_id: str, task_text: str, submitted_by: str,
                   submitter_run_id: str | None = None) -> None:
    if _ensure_willow_on_path() is None:
        logger.debug("run_ledger open skipped: WILLOW_ROOT not found")
        return
    try:
        from core.run_ledger import current_run_id, open_run

        parent = submitter_run_id or current_run_id()
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


def _reap_stale(pg) -> None:
    import os as _os

    stale_s = int(_os.environ.get("KART_STALE_SECONDS", "3600"))
    exempt = [
        x.strip()
        for x in _os.environ.get("KART_REAP_EXEMPT_IDS", "").split(",")
        if x.strip()
    ]
    reaped = pg.reap_stale_tasks(max_age_seconds=stale_s, exempt_ids=exempt)
    if reaped:
        logger.warning("kart reaped stale running tasks: %s", reaped)


_LAST_PRUNE_MONO: float = 0.0


def _maybe_prune_completed(pg) -> None:
    """Periodically delete old terminal task rows (batch lane bloat)."""
    import os as _os
    import time as _time

    global _LAST_PRUNE_MONO
    interval = int(_os.environ.get("KART_TASK_PRUNE_INTERVAL", "3600"))
    if interval <= 0:
        return
    now = _time.monotonic()
    if _LAST_PRUNE_MONO and (now - _LAST_PRUNE_MONO) < interval:
        return
    _LAST_PRUNE_MONO = now
    days = int(_os.environ.get("KART_TASK_RETENTION_DAYS", "7"))
    limit = int(_os.environ.get("KART_TASK_PRUNE_LIMIT", "500"))
    try:
        deleted = pg.prune_completed_tasks(days=days, limit=limit)
        if deleted:
            logger.info("kart pruned %d completed task row(s) older than %dd", deleted, days)
    except Exception as e:
        logger.warning("kart task prune failed: %s", e)


def _process_task_row(row: dict, *, context: str = "daemon") -> None:
    """Execute one claimed row; uses a dedicated PgBridge (thread-safe per connection)."""
    from core.kart_execute import execute_task_row, kart_timeout
    from core.pg_bridge import PgBridge

    pg = PgBridge()
    task_id = row["id"]
    task_text = row.get("task") or ""
    submitted_by = row.get("submitted_by") or "?"
    try:
        logger.info(
            "kart claimed %s (by %s): %s",
            task_id,
            submitted_by,
            task_text[:60],
        )
        _kart_run_open(
            task_id, task_text, submitted_by,
            submitter_run_id=row.get("submitter_run_id"),
        )
        status, result = execute_task_row(
            row, pg, timeout=kart_timeout(context), context=context
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
        logger.error("kart task %s error: %s", task_id, e)
        try:
            pg.task_complete(
                task_id,
                {"error": str(e), "context": f"{context}_exception"},
                "failed",
            )
        except Exception:
            pass
        _kart_run_close(task_id, "crashed")
    finally:
        try:
            pg.close()
        except Exception:
            pass


def _maybe_reload_self() -> None:
    _self_path = Path(__file__)
    if not hasattr(_maybe_reload_self, "_mtime"):
        _maybe_reload_self._mtime = _self_path.stat().st_mtime  # type: ignore[attr-defined]
    _cur_mtime = _self_path.stat().st_mtime
    if _cur_mtime != _maybe_reload_self._mtime:  # type: ignore[attr-defined]
        _maybe_reload_self._mtime = _cur_mtime  # type: ignore[attr-defined]
        _mod = sys.modules.get(__name__)
        if _mod is not None:
            try:
                importlib.reload(_mod)
                logger.info("kart_worker reloaded from disk")
            except Exception as re:
                logger.warning("kart_worker reload failed: %s", re)


def _kart_loop_batch(interval: int, pg) -> None:
    """One batch task at a time — does not block fast workers in other processes."""
    from core.kart_lanes import KART_LANE_BATCH

    active_task_id: str | None = None
    while True:
        try:
            _maybe_write_heartbeat()
            _maybe_reload_self()
            _reap_stale(pg)
            _maybe_prune_completed(pg)
            claimed = pg.claim_kart_tasks(limit=1, lane=KART_LANE_BATCH)
            if not claimed:
                time.sleep(interval)
                continue
            row = claimed[0]
            active_task_id = row["id"]
            _process_task_row(row, context="daemon")
            active_task_id = None
        except Exception as e:
            logger.error("kart batch loop error: %s", e)
            if pg is not None and active_task_id:
                try:
                    pg.task_complete(
                        active_task_id,
                        {"error": str(e), "context": "daemon_exception"},
                        "failed",
                    )
                except Exception:
                    pass
                active_task_id = None
            try:
                pg.close()
            except Exception:
                pass
            pg = None
            from core.pg_bridge import PgBridge

            pg = PgBridge()
            time.sleep(interval)


def _kart_loop_fast(interval: int, pg) -> None:
    """Concurrent fast-lane executor — gh/git/shell never wait on batch."""
    from core.kart_lanes import KART_LANE_FAST, fast_worker_slots

    max_workers = fast_worker_slots()
    in_flight: set[str] = set()
    lock = threading.Lock()
    pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="kart-fast")

    def _run(row: dict) -> None:
        try:
            _process_task_row(row, context="daemon")
        finally:
            with lock:
                in_flight.discard(row["id"])

    while True:
        try:
            _maybe_write_heartbeat()
            _maybe_reload_self()
            _reap_stale(pg)
            _maybe_prune_completed(pg)
            with lock:
                slots = max_workers - len(in_flight)
            if slots > 0:
                claimed = pg.claim_kart_tasks(limit=slots, lane=KART_LANE_FAST)
                for row in claimed:
                    with lock:
                        in_flight.add(row["id"])
                    pool.submit(_run, row)
            sleep_s = 0.5 if in_flight else interval
            time.sleep(sleep_s)
        except Exception as e:
            logger.error("kart fast loop error: %s", e)
            try:
                pg.close()
            except Exception:
                pass
            from core.pg_bridge import PgBridge

            pg = PgBridge()
            time.sleep(interval)


def _kart_loop_legacy(interval: int, pg) -> None:
    """Deprecated: single-threaded fast-then-batch (KART_WORKER_LANE=all)."""
    from core.kart_lanes import KART_LANE_BATCH, KART_LANE_FAST

    active_task_id: str | None = None
    while True:
        try:
            _maybe_write_heartbeat()
            _maybe_reload_self()
            _reap_stale(pg)
            _maybe_prune_completed(pg)
            claimed = pg.claim_kart_tasks(limit=1, lane=KART_LANE_FAST)
            if not claimed:
                claimed = pg.claim_kart_tasks(limit=1, lane=KART_LANE_BATCH)
            if not claimed:
                time.sleep(interval)
                continue
            row = claimed[0]
            active_task_id = row["id"]
            _process_task_row(row, context="daemon")
            active_task_id = None
        except Exception as e:
            logger.error("kart legacy loop error: %s", e)
            if pg is not None and active_task_id:
                try:
                    pg.task_complete(
                        active_task_id,
                        {"error": str(e), "context": "daemon_exception"},
                        "failed",
                    )
                except Exception:
                    pass
                active_task_id = None
            try:
                pg.close()
            except Exception:
                pass
            from core.pg_bridge import PgBridge

            pg = PgBridge()
            time.sleep(interval)


def kart_loop(interval: int = 5) -> None:
    """Daemon loop — lane mode from KART_WORKER_LANE (default fast)."""
    from core.grove_gate import assert_grove
    from core.kart_lanes import (
        KART_WORKER_MODE_ALL,
        KART_WORKER_MODE_BATCH,
        KART_WORKER_MODE_FAST,
        fast_worker_slots,
        worker_mode,
    )
    from core.pg_bridge import PgBridge

    assert_grove("kart_worker")

    from core.kart_lanes import reaper_alignment_warning

    align_warn = reaper_alignment_warning()
    if align_warn:
        logger.warning("kart reaper alignment: %s", align_warn)

    mode = worker_mode()
    logger.info(
        "kart daemon started (poll=%ds, lane=%s, fast_workers=%s)",
        interval,
        mode,
        fast_worker_slots() if mode == KART_WORKER_MODE_FAST else "n/a",
    )
    global _HEARTBEAT_LAST_MONO
    _HEARTBEAT_LAST_MONO = 0.0
    _maybe_write_heartbeat(tick_ok=True)
    pg = PgBridge()
    if mode == KART_WORKER_MODE_FAST:
        _kart_loop_fast(interval, pg)
    elif mode == KART_WORKER_MODE_BATCH:
        _kart_loop_batch(interval, pg)
    elif mode == KART_WORKER_MODE_ALL:
        logger.warning("KART_WORKER_LANE=all is deprecated; use split fast/batch units")
        _kart_loop_legacy(interval, pg)
    else:
        raise RuntimeError(f"unsupported kart worker mode: {mode}")
