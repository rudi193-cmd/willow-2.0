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


def _open_flags() -> int:
    anchor = willow_home() / "session_anchor.json"
    if not anchor.is_file():
        return 0
    try:
        data = json.loads(anchor.read_text())
        return int(data.get("open_flags") or 0)
    except Exception:
        return 0


def _kart_counts() -> tuple[int, int, int]:
    try:
        from core.pg_bridge import get_connection, release_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT status, COUNT(*) FROM public.tasks "
                "WHERE agent = 'kart' GROUP BY status"
            )
            rows = {r[0]: r[1] for r in cur.fetchall()}
            running = int(rows.get("running", 0))
            pending = int(rows.get("pending", 0))
            cur.execute(
                "SELECT COUNT(*) FROM public.tasks "
                "WHERE agent = 'kart' AND status IN ('done', 'completed') "
                "AND updated_at >= CURRENT_DATE"
            )
            done_today = int(cur.fetchone()[0])
            return running, pending, done_today
        finally:
            release_connection(conn)
    except Exception:
        return 0, 0, 0


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
        from willow_store import WillowStore
        from willow.fylgja.willow_home import resolve_store_root

        root = os.environ.get(
            "WILLOW_STORE_ROOT",
            str(resolve_store_root(Path(__file__).resolve().parents[2])),
        )
        store = WillowStore(root)
        who = (agent or os.environ.get("WILLOW_AGENT") or "willow").strip()
        dream_state = store.get(f"{who}/dream", "state") or {}
        if dream_state.get("locked"):
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
    summary.open_flags = _open_flags()
    summary.running_tasks, summary.pending_tasks, summary.done_today = _kart_counts()
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
    if summary.pending_tasks or summary.running_tasks:
        lines.append(
            f"kart {summary.running_tasks} running, {summary.pending_tasks} pending"
        )
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
