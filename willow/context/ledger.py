"""
willow/context/ledger.py — Append-only session ledger (disk-persistent).

Stolen from: parcadei/Continuous-Claude-v3 (pre_compact_continuity.py, session_start_continuity.py)

Key ideas taken:
  - Ledger = disk-persistent JSONL log that survives context compression
  - Entries survive /compact because they're on disk, not in context
  - On SessionStart (resume/compact), load and inject recent entries as additionalContext
  - Pre-compact hook dumps a structured snapshot before compression

Willow adaptations:
  - Written to $WILLOW_HOME/ledger_{agent}_{date}.jsonl (per-agent, per-day)
  - Entry types: decision | action | observation | block | compact_snapshot
  - No external deps (pure stdlib)
  - Wired into prompt_submit.py (human turns → observation) and
    pre_tool.py (blocked actions → block entry)
  - load_recent() returns last N entries formatted for additionalContext injection

Entry schema (JSONL, one JSON object per line):
  {
    "ts": "2026-05-09T...",
    "type": "decision" | "action" | "observation" | "block" | "compact_snapshot",
    "agent": "hanuman",
    "session_id": "...",
    "content": "..."
  }

No new deps required.
"""

from __future__ import annotations

import json
from core.agent_identity import require_agent_name
from datetime import datetime, timezone
from pathlib import Path

from willow.fylgja.willow_home import willow_home

_AGENT = require_agent_name()
_WILLOW_HOME = willow_home()

# How many recent entries to surface on context resume
_RESUME_ENTRY_LIMIT = 10
# Max chars of content per entry when building resume context
_CONTENT_TRUNCATE = 200
# Entry types
DECISION = "decision"
ACTION = "action"
OBSERVATION = "observation"
BLOCK = "block"
COMPACT_SNAPSHOT = "compact_snapshot"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _ledger_path(agent: str = _AGENT, date: str | None = None) -> Path:
    """Return $WILLOW_HOME/ledger_{agent}_{date}.jsonl for today."""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _WILLOW_HOME.mkdir(parents=True, exist_ok=True)
    return _WILLOW_HOME / f"ledger_{agent}_{date}.jsonl"


# ---------------------------------------------------------------------------
# Core write
# ---------------------------------------------------------------------------

def append(
    content: str,
    *,
    entry_type: str,
    session_id: str = "",
    agent: str = _AGENT,
) -> Path:
    """
    Append one entry to today's ledger.

    Returns the ledger path (useful for logging).
    This is the only write path — always append-only.
    """
    path = _ledger_path(agent)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": entry_type,
        "agent": agent,
        "session_id": session_id[:16] if session_id else "",
        "content": content[:2000],  # hard cap to keep file sane
    }
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # fail silently — ledger is advisory, never blocking
    return path


# ---------------------------------------------------------------------------
# Typed convenience wrappers
# ---------------------------------------------------------------------------

def log_observation(content: str, *, session_id: str = "") -> None:
    """Log a human turn or notable system observation."""
    if content and len(content.strip()) >= 4:
        append(content.strip()[:500], entry_type=OBSERVATION, session_id=session_id)


def log_decision(content: str, *, session_id: str = "") -> None:
    """Log an architectural or planning decision."""
    append(content, entry_type=DECISION, session_id=session_id)


def log_action(content: str, *, session_id: str = "") -> None:
    """Log a significant tool invocation (write, edit, deploy)."""
    append(content, entry_type=ACTION, session_id=session_id)


def log_block(tool_name: str, reason: str, *, session_id: str = "") -> None:
    """Log a blocked tool invocation (pre_tool.py calls this)."""
    content = f"BLOCKED {tool_name}: {reason}"
    append(content[:800], entry_type=BLOCK, session_id=session_id)


def log_compact_snapshot(summary: str, *, session_id: str = "") -> None:
    """Log a pre-compact summary so context survives compaction."""
    append(summary, entry_type=COMPACT_SNAPSHOT, session_id=session_id)


# ---------------------------------------------------------------------------
# Read / resume
# ---------------------------------------------------------------------------

def load_recent(
    *,
    agent: str = _AGENT,
    limit: int = _RESUME_ENTRY_LIMIT,
    days: int = 2,
) -> list[dict]:
    """
    Load the most recent `limit` entries across today and yesterday.

    Returns entries oldest-first (so the resume context reads chronologically).
    """
    today = datetime.now(timezone.utc)
    entries: list[dict] = []

    for delta in range(days - 1, -1, -1):  # yesterday first, then today
        from datetime import timedelta
        day_str = (today - timedelta(days=delta)).strftime("%Y-%m-%d")
        path = _ledger_path(agent, day_str)
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        except OSError:
            pass

    # Keep only the latest `limit` entries
    return entries[-limit:]


def build_resume_context(
    *,
    agent: str = _AGENT,
    limit: int = _RESUME_ENTRY_LIMIT,
    current_session_id: str = "",
) -> str:
    """
    Build an additionalContext string from recent ledger entries.

    This is injected by SessionStart when source == 'compact' or 'resume'.
    Keeps it brief: last N entries, truncated content, no binary noise.

    Provenance stamp (memory-provenance step 1, ADR-20260715): load_recent()
    merges every entry the agent wrote across the last two days — including
    entries from OTHER concurrent sessions sharing this agent+day ledger file.
    Each entry already carries its origin session_id/agent on disk (see
    append()); this renderer used to discard both, so a resumed session could
    not tell a foreign session's line apart from something it said itself
    (the cross-session bleed defect — flag-cross-session-ledger-bleed-on-resume,
    caught live 2026-07-15). We now stamp every line that is NOT this session's
    own with ⟨sid·agent⟩ and an ambient disclaimer, mirroring the discipline the
    [CROSS-RUNTIME] block already carries in fylgja/cross_runtime.py.

    current_session_id (optional): when the SessionStart hook passes the live
    session id, entries from THIS session render clean (they are genuinely this
    conversation's own survived-compaction history) and only foreign entries are
    flagged. When it is absent every entry is stamped, so no line is ever
    surfaced without an origin — the guard degrades safe.
    """
    entries = load_recent(agent=agent, limit=limit)
    if not entries:
        return ""

    cur = (current_session_id or "")[:16]
    body: list[str] = []
    saw_foreign = False
    for e in entries:
        ts_raw = e.get("ts", "")
        ts = ts_raw[11:16] if len(ts_raw) >= 16 else ts_raw  # HH:MM
        etype = e.get("type", "?")[:12]
        content = (e.get("content") or "")[:_CONTENT_TRUNCATE]
        if not content:
            continue
        e_sid = e.get("session_id") or ""
        e_agent = e.get("agent") or ""
        if cur and e_sid == cur:
            tag = ""  # this session's own survived-compaction history
        else:
            # Foreign session, or caller did not stamp the current id: never
            # surface a ledger line without an origin marker.
            who = f"{e_sid[:8] or '????'}·{e_agent}" if (e_sid or e_agent) else "no-origin"
            tag = f" ⟨{who}⟩"
            saw_foreign = True
        body.append(f"  {ts} [{etype}]{tag} {content}")

    if not body:
        return ""

    lines = ["[LEDGER] Session history (most recent last):"]
    if saw_foreign:
        if cur:
            lines.append(
                "  (⟨sid·agent⟩ marks a DIFFERENT session's entry, injected by "
                "the SessionStart hook; unstamped lines are this session's own. "
                "Never report a ⟨…⟩ line as something you did or said.)"
            )
        else:
            lines.append(
                "  (entries may span multiple sessions; ⟨sid·agent⟩ marks each "
                "line's origin. A line whose sid is not this session's is ambient "
                "context, not your own memory.)"
            )
    lines.extend(body)
    lines.append(f"[LEDGER] {len(entries)} entries loaded.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Compact snapshot builder (called from pre_tool.py or a PreCompact hook)
# ---------------------------------------------------------------------------

def snapshot_for_compact(
    *,
    tool_name: str = "",
    files_touched: list[str] | None = None,
    session_id: str = "",
    note: str = "",
) -> None:
    """
    Write a compact-snapshot entry capturing what was happening before compaction.
    Mirrors the pre_compact_continuity.py approach from Continuous-Claude-v3.
    """
    parts: list[str] = []
    if note:
        parts.append(note)
    if files_touched:
        names = ", ".join(Path(f).name for f in files_touched[:8])
        if len(files_touched) > 8:
            names += f" (+{len(files_touched) - 8} more)"
        parts.append(f"files: {names}")
    if tool_name:
        parts.append(f"last tool: {tool_name}")

    summary = " | ".join(parts) if parts else "pre-compact snapshot (no details)"
    log_compact_snapshot(summary, session_id=session_id)
