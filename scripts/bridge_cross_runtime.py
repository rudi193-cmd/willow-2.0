#!/usr/bin/env python3
"""
Build cross-runtime handoff bridge from Claude + Cursor JSONL sessions.

Usage:
  python3 scripts/bridge_cross_runtime.py \\
    --claude 6e38bf78-7907-4d04-a45d-6d64ff08bb7c \\
    --cursor 91804daa-7082-4a23-8ce3-05182c36ac41

Writes ~/.willow/handoffs/cross-runtime.json and prints summary.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_indexer import parse_session

CLAUDE_ROOT = Path.home() / ".claude" / "projects" / "-home-sean-campbell-willow-2-0"
CURSOR_ROOT = (
    Path.home()
    / ".cursor"
    / "projects"
    / "home-sean-campbell-willow-2-0"
    / "agent-transcripts"
)

HANDOFF_DIR = Path.home() / "github" / ".willow" / "handoffs"
if not HANDOFF_DIR.is_dir():
    HANDOFF_DIR = Path.home() / ".willow" / "handoffs"
BRIDGE_PATH = HANDOFF_DIR / "cross-runtime.json"

# Live threads — keep in sync with handoffs/hanuman/session_handoff-2026-05-28d_hanuman.md
JELES_OPEN = [
    "GEMINI_API_KEY deferred (Groq + Ollama sufficient)",
    "Commit local path migration — safe-app-willow-grove, willow-2.0 scripts, .willow env",
    "Upstream PR #5 (claude-deep-review) — awaiting re-review",
    "Upstream PR #1032 (mcp-memory-service) — awaiting maintainer",
    "Willow stack rethink — design backlog (fuzzy)",
]

CURSOR_OPEN = [
    "Optional: prune grove worktrees dashboard-fresh / frank-ledger",
]


def _find_jsonl(session_id: str, runtime: str) -> Path | None:
    if runtime == "claude":
        p = CLAUDE_ROOT / f"{session_id}.jsonl"
        return p if p.is_file() else None
    if runtime == "cursor":
        folder = CURSOR_ROOT / session_id
        p = folder / f"{session_id}.jsonl"
        return p if p.is_file() else None
    return None


def _summarize(session_id: str, runtime: str) -> dict | None:
    path = _find_jsonl(session_id, runtime)
    if not path:
        return None
    meta = parse_session(str(path))
    if not meta:
        return None
    msgs = meta.get("user_messages") or []
    last = msgs[-1]["text"][:200] if msgs else ""
    first = msgs[0]["text"][:120] if msgs else ""
    tool_calls = json.loads(meta.get("tool_calls") or "{}")
    return {
        "session_id": session_id,
        "runtime": runtime,
        "file_path": str(path),
        "started_at": meta.get("started_at"),
        "ended_at": meta.get("ended_at"),
        "duration_minutes": meta.get("duration_minutes"),
        "turn_count": meta.get("turn_count"),
        "user_message_count": meta.get("user_message_count"),
        "compaction_count": meta.get("compaction_count"),
        "tool_calls": tool_calls,
        "first_topic": first.replace("\n", " "),
        "last_topic": last.replace("\n", " "),
        "summary": last.replace("\n", " ")[:160],
    }


def build_bridge(claude_id: str, cursor_id: str, extra_claude: list[str] | None = None) -> dict:
    claude = _summarize(claude_id, "claude") if claude_id else None
    cursor = _summarize(cursor_id, "cursor") if cursor_id else None

    open_threads = list(JELES_OPEN)
    if cursor:
        open_threads.extend(CURSOR_OPEN)

    # Evidence from Claude metadata → why Cursor MCP/Kart work matters
    evidence: list[str] = []
    if claude:
        tc = claude.get("tool_calls") or {}
        bash_n = tc.get("Bash", 0)
        mcp_n = tc.get("MCP_willow", 0)
        if bash_n:
            evidence.append(f"Claude session used Bash {bash_n}x vs MCP_willow {mcp_n}x — hooks+Kart target this")
        if claude.get("compaction_count"):
            evidence.append(f"Claude compactions: {claude['compaction_count']} (long session)")

    next_bite = JELES_OPEN[0]
    if cursor and cursor.get("last_topic", "").lower().find("kart") >= 0:
        next_bite = "Verify Kart smoke + land Cursor infra commits, then Jeles Binder wiring"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claude_latest": claude,
        "cursor_latest": cursor,
        "open_threads": open_threads,
        "evidence": evidence,
        "next_bite": next_bite,
        "extra_claude_sessions": extra_claude or [],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build cross-runtime handoff bridge JSON")
    ap.add_argument("--claude", default="6e38bf78-7907-4d04-a45d-6d64ff08bb7c")
    ap.add_argument("--cursor", default="91804daa-7082-4a23-8ce3-05182c36ac41")
    ap.add_argument("--claude-extra", action="append", default=[])
    args = ap.parse_args()

    bridge = build_bridge(args.claude, args.cursor, args.claude_extra)
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    BRIDGE_PATH.write_text(json.dumps(bridge, indent=2), encoding="utf-8")
    print(json.dumps({"written": str(BRIDGE_PATH), "next_bite": bridge.get("next_bite")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
