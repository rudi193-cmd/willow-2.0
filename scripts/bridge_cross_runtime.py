#!/usr/bin/env python3
"""
Build cross-runtime handoff bridge from Claude + Cursor JSONL sessions.

Usage:
  python3 scripts/bridge_cross_runtime.py
  python3 scripts/bridge_cross_runtime.py --agent willow
  python3 scripts/bridge_cross_runtime.py --claude <uuid> --cursor <uuid>

Writes $WILLOW_HOME/handoffs/cross-runtime.json and prints summary.
SessionStart injects [CROSS-RUNTIME] via willow/fylgja/cross_runtime.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(_REPO))

from core.agent_identity import require_agent_name
from sap.handoff_index import (
    extract_next_bite,
    scan_markdown_handoffs,
    select_best_handoff,
)
from sap.handoff_index import _parse_json_list
from willow.fylgja.willow_home import willow_home
from session_indexer import parse_session

from willow.fylgja.claude_projects import (
    CLAUDE_PROJECT_ROOTS,
    claude_jsonl_paths,
    find_claude_jsonl,
    latest_claude_session_id,
)

# Back-compat for tests that monkeypatch a single root.
CLAUDE_ROOT = CLAUDE_PROJECT_ROOTS[0]
CURSOR_ROOT = (
    Path.home()
    / ".cursor"
    / "projects"
    / "home-sean-campbell-willow-2-0"
    / "agent-transcripts"
)

HANDOFF_DIR = willow_home(_REPO) / "handoffs"
BRIDGE_PATH = HANDOFF_DIR / "cross-runtime.json"

# Substrings — drop handoff threads that reference shipped/closed work.
_RESOLVED_THREAD_MARKERS = (
    "FORK-CE988743",
    "cross-runtime.json",
    "fix/identity-drift",
    "#434",
    "#435",
    "PR #5 (claude-deep-review)",
    "PR #1032 (mcp-memory-service)",
    "GEMINI_API_KEY deferred",
    "Commit local path migration",
    "Willow stack rethink",
)


def _claude_jsonl_paths() -> list[Path]:
    return claude_jsonl_paths()


def _find_jsonl(session_id: str, runtime: str) -> Path | None:
    if runtime == "claude":
        return find_claude_jsonl(session_id)
    if runtime == "cursor":
        folder = CURSOR_ROOT / session_id
        p = folder / f"{session_id}.jsonl"
        return p if p.is_file() else None
    return None


def latest_session_id(runtime: str) -> str:
    """Most recently modified session id for claude or cursor, or '' if none."""
    if runtime == "claude":
        return latest_claude_session_id()
    if runtime == "cursor":
        if not CURSOR_ROOT.is_dir():
            return ""
        best_id = ""
        best_mtime = 0.0
        for folder in CURSOR_ROOT.iterdir():
            if not folder.is_dir():
                continue
            jl = folder / f"{folder.name}.jsonl"
            if jl.is_file():
                mtime = jl.stat().st_mtime
                if mtime > best_mtime:
                    best_mtime = mtime
                    best_id = folder.name
        return best_id
    return ""


def _handoff_fields(agent: str) -> tuple[list[str], str, str]:
    """Return (open_threads, next_bite, handoff_filename) from richest handoff markdown."""
    candidates = scan_markdown_handoffs(agent, HANDOFF_DIR)
    best = select_best_handoff(candidates)
    if not best:
        return [], "", ""
    threads = [str(t).strip() for t in _parse_json_list(best.get("open_threads")) if str(t).strip()]
    questions = _parse_json_list(best.get("questions"))
    summary = str(best.get("summary") or "")
    bite = extract_next_bite(questions, summary)
    return threads, bite, str(best.get("filename") or "")


def prune_resolved_threads(threads: list[str]) -> list[str]:
    """Drop handoff lines that reference work already shipped."""
    kept: list[str] = []
    for item in threads:
        if any(marker.lower() in item.lower() for marker in _RESOLVED_THREAD_MARKERS):
            continue
        kept.append(item)
    return kept


def _clean_thread_line(text: str) -> str:
    import re

    t = text.strip()
    t = re.sub(r"^\*+", "", t).strip()
    t = re.sub(r"\*+", "", t)
    return t.strip()


def _pick_next_bite(threads: list[str], handoff_bite: str) -> str:
    if handoff_bite:
        normalized = handoff_bite.strip().lower().rstrip("?")
        if normalized not in ("what is the next single bite",):
            return _clean_thread_line(handoff_bite)
    for needle in ("willow_run",):
        for item in threads:
            if needle in item.lower():
                return _clean_thread_line(item)
    if threads:
        return _clean_thread_line(threads[0])
    return "willow_run triple output — context burn dedup (P2)"


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


def build_bridge(
    *,
    agent: str,
    claude_id: str = "",
    cursor_id: str = "",
    extra_claude: list[str] | None = None,
    prune: bool = True,
) -> dict:
    claude_id = claude_id or latest_session_id("claude")
    cursor_id = cursor_id or latest_session_id("cursor")
    claude = _summarize(claude_id, "claude") if claude_id else None
    cursor = _summarize(cursor_id, "cursor") if cursor_id else None

    raw_threads, handoff_bite, handoff_file = _handoff_fields(agent)
    open_threads = prune_resolved_threads(raw_threads) if prune else list(raw_threads)

    evidence: list[str] = []
    if handoff_file:
        evidence.append(f"handoff source: {handoff_file}")
    if claude:
        tc = claude.get("tool_calls") or {}
        bash_n = tc.get("Bash", 0)
        mcp_n = tc.get("MCP_willow", 0)
        if bash_n or mcp_n:
            evidence.append(
                f"Claude session {claude_id[:8]}: Bash {bash_n}× vs MCP_willow {mcp_n}×"
            )
        if claude.get("compaction_count"):
            evidence.append(f"Claude compactions: {claude['compaction_count']}")
    if cursor:
        tc = cursor.get("tool_calls") or {}
        bash_n = tc.get("Bash", 0)
        mcp_n = tc.get("MCP_willow", 0)
        if bash_n or mcp_n:
            evidence.append(
                f"Cursor session {cursor_id[:8]}: Bash {bash_n}× vs MCP_willow {mcp_n}×"
            )

    next_bite = _pick_next_bite(open_threads, handoff_bite)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "handoff_source": handoff_file,
        "claude_latest": claude,
        "cursor_latest": cursor,
        "open_threads": open_threads,
        "evidence": evidence,
        "next_bite": next_bite,
        "extra_claude_sessions": extra_claude or [],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build cross-runtime handoff bridge JSON")
    ap.add_argument("--agent", default="", help="Fleet agent for handoff scan (default: WILLOW_AGENT_NAME)")
    ap.add_argument("--claude", default="", help="Claude session UUID (default: latest by mtime)")
    ap.add_argument("--cursor", default="", help="Cursor session UUID (default: latest by mtime)")
    ap.add_argument("--claude-extra", action="append", default=[])
    ap.add_argument("--no-prune", action="store_true", help="Keep resolved/shipped threads from handoff")
    args = ap.parse_args()

    agent = args.agent or require_agent_name()
    bridge = build_bridge(
        agent=agent,
        claude_id=args.claude,
        cursor_id=args.cursor,
        extra_claude=args.claude_extra,
        prune=not args.no_prune,
    )
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    BRIDGE_PATH.write_text(json.dumps(bridge, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "written": str(BRIDGE_PATH),
                "agent": agent,
                "claude": (bridge.get("claude_latest") or {}).get("session_id", ""),
                "cursor": (bridge.get("cursor_latest") or {}).get("session_id", ""),
                "open_threads": len(bridge.get("open_threads") or []),
                "next_bite": bridge.get("next_bite"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
