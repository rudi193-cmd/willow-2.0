"""Native reimplementation of cctime's stuck-loop chain detector.

Walks a Claude Code session JSONL transcript, pairs each tool_use with its
tool_result, and flags chains of consecutive same-tool calls where every
call before the last one in the chain errored.

Reimplements the algorithm at dioptx/cctime's src/analyzer.ts:395-474
(reviewed 2026-07-05, decision recorded in
project-dioptx-tooling-integration-decision.md) natively against the same
JSONL Willow already resolves via willow.fylgja.claude_projects, rather than
depending on the TS tool itself. Retrospective (parses a transcript after
the fact) — complementary to sentinel_watchdog's live heartbeat, which
catches silence rather than thrashing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ToolCall:
    tool_name: str
    start_ts: float
    end_ts: float
    is_error: bool


@dataclass
class StuckLoop:
    tool_name: str
    attempts: int
    failures: int
    duration_ms: float
    start_time: float
    end_time: float
    resolved: bool

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "attempts": self.attempts,
            "failures": self.failures,
            "duration_ms": self.duration_ms,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "resolved": self.resolved,
        }


def _parse_ts(value: str | None) -> float | None:
    """Parse a Claude Code JSONL ISO-8601 timestamp to epoch milliseconds
    (matching JS's Date.parse(), which the upstream algorithm uses)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000
    except ValueError:
        return None


def _content_array(message: dict) -> list[dict]:
    content = (message.get("message") or {}).get("content")
    return content if isinstance(content, list) else []


def extract_tool_calls(messages: list[dict]) -> list[ToolCall]:
    """Pair each tool_use with its tool_result, in transcript order."""
    starts: dict[str, tuple[str, float]] = {}
    calls: list[ToolCall] = []

    for msg in messages:
        ts = _parse_ts(msg.get("timestamp"))
        if ts is None:
            continue

        msg_type = msg.get("type")
        if msg_type == "assistant":
            for c in _content_array(msg):
                if c.get("type") == "tool_use" and c.get("id") and c.get("name"):
                    starts[c["id"]] = (c["name"], ts)
        elif msg_type == "user":
            for c in _content_array(msg):
                if c.get("type") == "tool_result" and c.get("tool_use_id"):
                    start = starts.pop(c["tool_use_id"], None)
                    if start is not None:
                        name, start_ts = start
                        calls.append(
                            ToolCall(
                                tool_name=name,
                                start_ts=start_ts,
                                end_ts=ts,
                                is_error=bool(c.get("is_error")),
                            )
                        )
    return calls


def detect_stuck_loops(calls: list[ToolCall], *, min_failures: int = 2) -> list[StuckLoop]:
    """Chain consecutive same-tool calls while the prior call in the chain
    errored; flag chains with >= min_failures errors. Mirrors analyzer.ts's
    chainEnd-extension logic exactly — the chain's final call may or may not
    itself have errored (captured in `resolved`)."""
    loops: list[StuckLoop] = []
    chain_start = 0
    n = len(calls)

    while chain_start < n:
        tool_name = calls[chain_start].tool_name
        chain_end = chain_start

        while (
            chain_end + 1 < n
            and calls[chain_end + 1].tool_name == tool_name
            and calls[chain_end].is_error
        ):
            chain_end += 1

        chain_calls = calls[chain_start : chain_end + 1]
        failures = sum(1 for c in chain_calls if c.is_error)

        if failures >= min_failures:
            loops.append(
                StuckLoop(
                    tool_name=tool_name,
                    attempts=len(chain_calls),
                    failures=failures,
                    duration_ms=chain_calls[-1].end_ts - chain_calls[0].start_ts,
                    start_time=chain_calls[0].start_ts,
                    end_time=chain_calls[-1].end_ts,
                    resolved=not chain_calls[-1].is_error,
                )
            )

        chain_start = chain_end + 1

    return loops


def load_jsonl_messages(path: Path) -> list[dict]:
    messages: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return messages


def detect_stuck_loops_in_jsonl(path: Path, *, min_failures: int = 2) -> list[StuckLoop]:
    calls = extract_tool_calls(load_jsonl_messages(path))
    return detect_stuck_loops(calls, min_failures=min_failures)
