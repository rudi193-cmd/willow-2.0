"""desk_attention.py — Agent-facing attention summary (mirrors Grove desk cockpit)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from willow.fylgja.willow_home import willow_home


@dataclass
class AttentionSummary:
    mentions: list[dict] = field(default_factory=list)
    open_flags: int = 0
    nest_pending: int = 0
    running_tasks: int = 0
    pending_tasks: int = 0
    pending_fast: int = 0
    pending_batch: int = 0
    running_fast: int = 0
    running_batch: int = 0
    oldest_pending_fast_s: int = 0
    oldest_pending_batch_s: int = 0
    detached_running: int = 0
    done_today: int = 0
    dream_due: bool = False
    human_required_open: int = 0
    human_required: list[dict] = field(default_factory=list)
    operator_load: dict = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)


def _nest_pending() -> int:
    queue = willow_home() / "nest-queue.json"
    if not queue.is_file():
        return 0
    try:
        items = json.loads(queue.read_text())
        return sum(1 for i in items if i.get("status") == "pending")
    except Exception:
        return 0


def _open_flags(agent: str = "") -> int:
    """Live count of open {agent}/gaps + {agent}/flags (mirrors session_start._open_attention_items).

    Previously read a cached session_anchor.json written under a filename
    (session_anchor_path()) that nothing here ever matched, so this always
    reported 0 regardless of actual open flags.
    """
    who = (agent or os.environ.get("WILLOW_AGENT") or "willow").strip()
    try:
        from core.store_port import get_store_port
        from willow.fylgja.willow_home import resolve_store_root

        root = os.environ.get(
            "WILLOW_STORE_ROOT",
            str(resolve_store_root(Path(__file__).resolve().parents[2])),
        )
        store = get_store_port(root=root)
        count = 0
        for gap in store.all(f"{who}/gaps") or []:
            if gap.get("status") == "open":
                count += 1
        for flag in store.all(f"{who}/flags") or []:
            if flag.get("flag_state") != "open":
                continue
            title = str(flag.get("title") or "")
            if title.startswith("Blessed path"):
                continue
            count += 1
        return count
    except Exception:
        return 0


def _kart_counts() -> tuple[int, int, int, dict]:
    """Return running, pending, done_today, and lane/detached detail."""
    extra: dict = {}
    try:
        from core.kart_lanes import reaper_stale_seconds
        from core.pg_bridge import get_connection, release_connection

        conn = get_connection()
        try:
            stale_s = reaper_stale_seconds()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'running') AS running,
                    COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                    COUNT(*) FILTER (WHERE status = 'pending' AND lane = 'fast') AS pending_fast,
                    COUNT(*) FILTER (WHERE status = 'pending' AND lane = 'batch') AS pending_batch,
                    COUNT(*) FILTER (WHERE status = 'running' AND lane = 'fast') AS running_fast,
                    COUNT(*) FILTER (WHERE status = 'running' AND lane = 'batch') AS running_batch,
                    COALESCE(
                        EXTRACT(EPOCH FROM (
                            now() - MIN(created_at) FILTER (
                                WHERE status = 'pending' AND lane = 'fast'
                            )
                        )),
                        0
                    )::int AS oldest_pending_fast_s,
                    COALESCE(
                        EXTRACT(EPOCH FROM (
                            now() - MIN(created_at) FILTER (
                                WHERE status = 'pending' AND lane = 'batch'
                            )
                        )),
                        0
                    )::int AS oldest_pending_batch_s,
                    COUNT(*) FILTER (
                        WHERE status = 'running'
                          AND result IS NULL
                          AND updated_at < now() - make_interval(secs => %s)
                    ) AS stale_running
                FROM public.tasks
                WHERE agent = 'kart'
                """,
                (stale_s,),
            )
            row = cur.fetchone()
            running = int(row[0] or 0)
            pending = int(row[1] or 0)
            extra = {
                "pending_fast": int(row[2] or 0),
                "pending_batch": int(row[3] or 0),
                "running_fast": int(row[4] or 0),
                "running_batch": int(row[5] or 0),
                "oldest_pending_fast_s": int(row[6] or 0),
                "oldest_pending_batch_s": int(row[7] or 0),
                "stale_running": int(row[8] or 0),
            }
            cur.execute(
                "SELECT COUNT(*) FROM public.tasks "
                "WHERE agent = 'kart' AND status IN ('done', 'completed') "
                "AND updated_at >= CURRENT_DATE"
            )
            done_today = int(cur.fetchone()[0])
            return running, pending, done_today, extra
        finally:
            release_connection(conn)
    except Exception:
        return 0, 0, 0, extra


def _detached_running() -> int:
    try:
        from core.kart_detached import list_detached

        return sum(1 for j in list_detached(limit=100) if j.get("state") == "running")
    except Exception:
        return 0


def _human_required(limit: int = 5) -> tuple[int, list[dict], dict]:
    try:
        from core.human_required import list_items, operator_load_state, stats
        from core.pg_bridge import get_connection, release_connection

        conn = get_connection()
        try:
            summary = stats(conn)
            open_total = int(summary.get("open_total") or 0)
            items = list_items(conn, status="open", limit=limit)
            return open_total, items, operator_load_state(conn)
        finally:
            release_connection(conn)
    except Exception:
        return 0, [], {}


def _dream_due(agent: str = "") -> bool:
    try:
        from core.store_port import get_store_port
        from willow.fylgja.willow_home import resolve_store_root

        root = os.environ.get(
            "WILLOW_STORE_ROOT",
            str(resolve_store_root(Path(__file__).resolve().parents[2])),
        )
        from core.lock_ttl import lock_is_live

        store = get_store_port(root=root)
        who = (agent or os.environ.get("WILLOW_AGENT") or "willow").strip()
        dream_state = store.get(f"{who}/dream", "state") or {}
        if lock_is_live(dream_state):
            return False
        last_str = dream_state.get("last_dream_at", "")
        if not last_str:
            return True
        last = datetime.fromisoformat(last_str.replace("Z", "+00:00"))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last).total_seconds() / 3600 >= 24
    except Exception:
        return False


def fetch_attention_summary(
    *,
    agent: str = "",
    inbox: list[dict] | None = None,
) -> AttentionSummary:
    """Build attention summary. Pass inbox rows from grove_inbox when available."""
    summary = AttentionSummary()
    summary.nest_pending = _nest_pending()
    summary.open_flags = _open_flags(agent)
    summary.running_tasks, summary.pending_tasks, summary.done_today, kart_extra = _kart_counts()
    summary.pending_fast = int(kart_extra.get("pending_fast", 0))
    summary.pending_batch = int(kart_extra.get("pending_batch", 0))
    summary.running_fast = int(kart_extra.get("running_fast", 0))
    summary.running_batch = int(kart_extra.get("running_batch", 0))
    summary.oldest_pending_fast_s = int(kart_extra.get("oldest_pending_fast_s", 0))
    summary.oldest_pending_batch_s = int(kart_extra.get("oldest_pending_batch_s", 0))
    summary.detached_running = _detached_running()
    summary.dream_due = _dream_due(agent)
    (
        summary.human_required_open,
        summary.human_required,
        summary.operator_load,
    ) = _human_required()

    if inbox:
        summary.mentions = [
            m for m in inbox
            if isinstance(m, dict) and not m.get("error")
        ][:10]

    lines: list[str] = []
    if summary.mentions:
        lines.append(f"{len(summary.mentions)} grove inbox")
    if summary.open_flags:
        lines.append(f"{summary.open_flags} open flags")
    if summary.nest_pending:
        lines.append(f"{summary.nest_pending} nest pending")
    if summary.pending_tasks or summary.running_tasks or summary.detached_running:
        parts = []
        if summary.pending_fast or summary.running_fast:
            wait = ""
            if summary.pending_fast and summary.oldest_pending_fast_s:
                wait = f", oldest wait {summary.oldest_pending_fast_s}s"
            parts.append(
                f"fast {summary.running_fast}↑/{summary.pending_fast}⏳{wait}"
            )
        if summary.pending_batch or summary.running_batch:
            wait = ""
            if summary.pending_batch and summary.oldest_pending_batch_s:
                wait = f", oldest wait {summary.oldest_pending_batch_s}s"
            parts.append(
                f"batch {summary.running_batch}↑/{summary.pending_batch}⏳{wait}"
            )
        if summary.detached_running:
            parts.append(f"detached {summary.detached_running}↑")
        if int(kart_extra.get("stale_running", 0)):
            parts.append(f"{kart_extra['stale_running']} stale")
        lines.append("kart " + " · ".join(parts))
    if summary.dream_due:
        lines.append("dream overdue")
    if summary.human_required_open:
        lines.append(f"{summary.human_required_open} human-required")
    load_level = (summary.operator_load or {}).get("level")
    if load_level and load_level not in {"clear", "watch"}:
        lines.append(f"operator load {load_level}")
    if not lines:
        lines.append("all clear")
    summary.lines = lines
    return summary


def attention_as_dict(summary: AttentionSummary | None = None, **kwargs) -> dict:
    s = summary or fetch_attention_summary(**kwargs)
    return asdict(s)
