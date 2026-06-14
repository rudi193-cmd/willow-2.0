#!/usr/bin/env python3
"""Normalize cartographer CBM prompt runs into a benchmark sidecar.

This is a focused sidecar for the "Willow citadel cartographer" prompt family.
It does not mutate the older broad Claude benchmark artifacts.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NEST = Path(__file__).resolve().parent
PROJECT = Path.home() / ".claude" / "projects" / "-home-sean-campbell-github-willow-2-0"

SIDECAR_DB = NEST / "cartographer_code_memory_sidecar.db"
REPORT_JSON = NEST / "cartographer_code_memory_runs.json"
REPORT_MD = NEST / "cartographer_code_memory_runs.md"

PROMPT_MARKER = "apprentice cartographer entering the Willow citadel"
ENDING = "Ready for boot when the map is safe."

SESSIONS = [
    "3be26281-0fbc-4859-ae2a-adbb46bcae1a",
    "ca94f61b-5b7f-4a94-b444-11eca76b92ab",
    "52919736-28c9-4336-a9cd-907d3531f940",
    "0a0800e2-c74d-4aa6-a0c1-7fb50fdd92e0",
    "006b591b-b4a2-43f8-ab8c-f1d9c7591b98",
    "6ec7c116-5ccc-4438-b9e1-df911a231aca",
    "c0bfe520-23d6-42df-b008-5f3c42557eae",
    "10dc47a6-c08b-4ffa-823e-b5bb857f7916",
]

RAW_TOOLS = {
    "Shell",
    "Bash",
    "Read",
    "Grep",
    "Glob",
    "Write",
    "Edit",
    "MultiEdit",
    "ApplyPatch",
    "StrReplace",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


def active_minutes(timestamps: list[datetime], gap_cap_min: int = 20) -> float | None:
    if len(timestamps) < 2:
        return None
    timestamps = sorted(timestamps)
    seconds = 0.0
    cap = gap_cap_min * 60
    for prev, cur in zip(timestamps, timestamps[1:]):
        gap = (cur - prev).total_seconds()
        if gap > 0:
            seconds += min(gap, cap)
    return round(seconds / 60, 2)


def count_refs(text: str) -> int:
    refs: set[str] = set()
    for match in re.findall(r"`([^`]+)`", text):
        if "/" in match or "::" in match or match.endswith((".py", ".sh", ".md", ".json")):
            refs.add(match)
    # Also catch unquoted file paths in the story prose.
    for match in re.findall(r"\b(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+(?:\.py|\.sh|\.md|\.json)\b", text):
        refs.add(match)
    return len(refs)


def primary_model(models: Counter[str]) -> str:
    if not models:
        return "unknown"
    return models.most_common(1)[0][0]


def short_model(model: str) -> str:
    if "opus" in model:
        return "opus"
    if "sonnet" in model:
        return "sonnet"
    if "haiku" in model:
        return "haiku"
    return model


def scan_session(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    timestamps: list[datetime] = []
    models: Counter[str] = Counter()
    tools: Counter[str] = Counter()
    cbm_tools: Counter[str] = Counter()
    input_tokens = output_tokens = cache_read_tokens = cache_write_tokens = 0
    first_prompt = ""
    field_report_text = ""
    user_turns = assistant_turns = 0

    for row in rows:
        ts = parse_ts(row.get("timestamp"))
        if ts:
            timestamps.append(ts)

        if row.get("type") == "user":
            user_turns += 1
            msg = row.get("message") if isinstance(row.get("message"), dict) else {}
            text = text_from_content(msg.get("content"))
            if not first_prompt and PROMPT_MARKER in text:
                first_prompt = " ".join(text.split())

        msg = row.get("message") if isinstance(row.get("message"), dict) else {}
        if not msg:
            continue
        if msg.get("model"):
            models[msg["model"]] += 1
            assistant_turns += 1
        usage = msg.get("usage") if isinstance(msg.get("usage"), dict) else {}
        input_tokens += int(usage.get("input_tokens") or 0)
        output_tokens += int(usage.get("output_tokens") or 0)
        cache_read_tokens += int(usage.get("cache_read_input_tokens") or 0)
        cache_write_tokens += int(usage.get("cache_creation_input_tokens") or 0)

        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "tool_use":
                    name = part.get("name") or "unknown"
                    tools[name] += 1
                    if name.startswith("mcp__codebase-memory-mcp__"):
                        cbm_tools[name.split("__")[-1]] += 1
                elif part.get("type") == "text":
                    text = part.get("text") or ""
                    if "FIELD REPORT" in text or "Field Report" in text or ENDING in text:
                        field_report_text = text

    first_ts = min(timestamps).isoformat() if timestamps else None
    last_ts = max(timestamps).isoformat() if timestamps else None
    dur_min = None
    if len(timestamps) >= 2:
        dur_min = round((max(timestamps) - min(timestamps)).total_seconds() / 60, 2)

    cbm_calls = sum(cbm_tools.values())
    willow_calls = sum(count for name, count in tools.items() if name.startswith("mcp__willow__"))
    raw_calls = sum(count for name, count in tools.items() if name in RAW_TOOLS)
    semantic_calls = 0
    for row in rows:
        msg = row.get("message") if isinstance(row.get("message"), dict) else {}
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "tool_use":
                continue
            if (part.get("name") or "").endswith("search_graph") and "semantic_query" in str(part.get("input") or {}):
                semantic_calls += 1

    report_text_lower = field_report_text.lower()
    concrete_refs = count_refs(field_report_text)
    criteria = {
        "used_cbm_not_raw": cbm_calls > 0 and raw_calls == 0,
        "called_get_architecture": cbm_tools["get_architecture"] >= 1,
        "called_trace_path_three": cbm_tools["trace_path"] >= 3,
        "used_semantic_search": semantic_calls >= 1,
        "used_detect_changes": cbm_tools["detect_changes"] >= 1,
        "zero_willow_tools": willow_calls == 0,
        "three_concrete_refs": concrete_refs >= 3,
        "exact_ending": ENDING in field_report_text,
        "states_uncertainty": any(word in report_text_lower for word in ("uncertain", "uncertainty", "caveat", "limitation", "unknown")),
        "danger_justified": any(word in report_text_lower for word in ("danger", "dangerous", "risky", "risk")),
    }

    return {
        "session_uid": path.stem,
        "short": path.stem[:8],
        "path": str(path),
        "prompt_family": "cartographer_code_memory",
        "session_date": first_ts[:10] if first_ts else None,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "dur_min": dur_min,
        "active_min_gap_cap_20": active_minutes(timestamps),
        "model": primary_model(models),
        "model_group": short_model(primary_model(models)),
        "models_seen": dict(models),
        "user_turns": user_turns,
        "assistant_turns": assistant_turns,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "tool_calls": sum(tools.values()),
        "tool_histogram": dict(tools),
        "cbm_tool_histogram": dict(cbm_tools),
        "cbm_calls": cbm_calls,
        "willow_calls": willow_calls,
        "raw_tool_calls": raw_calls,
        "bash_calls": tools["Bash"],
        "agent_calls": tools["Agent"],
        "semantic_search_calls": semantic_calls,
        "field_report": bool(field_report_text),
        "ending_exact": ENDING in field_report_text,
        "concrete_refs": concrete_refs,
        "criteria": criteria,
        "score_10": sum(1 for passed in criteria.values() if passed),
        "cbm_only_pass": cbm_calls > 0 and willow_calls == 0 and raw_calls == 0,
        "prompt_excerpt": first_prompt[:180],
    }


def write_db(runs: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    if SIDECAR_DB.exists():
        SIDECAR_DB.unlink()
    con = sqlite3.connect(SIDECAR_DB)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(
        """
        CREATE TABLE runs (
            session_uid TEXT PRIMARY KEY,
            short TEXT NOT NULL,
            model TEXT NOT NULL,
            model_group TEXT NOT NULL,
            session_date TEXT,
            dur_min REAL,
            active_min_gap_cap_20 REAL,
            tool_calls INTEGER,
            cbm_calls INTEGER,
            willow_calls INTEGER,
            raw_tool_calls INTEGER,
            semantic_search_calls INTEGER,
            score_10 INTEGER,
            cbm_only_pass INTEGER,
            field_report INTEGER,
            ending_exact INTEGER,
            concrete_refs INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            cache_write_tokens INTEGER,
            path TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE run_tools (
            session_uid TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            count INTEGER NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY (session_uid, tool_name, source)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE run_criteria (
            session_uid TEXT NOT NULL,
            criterion TEXT NOT NULL,
            passed INTEGER NOT NULL,
            PRIMARY KEY (session_uid, criterion)
        )
        """
    )
    con.execute("CREATE TABLE summary (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)")
    for run in runs:
        con.execute(
            """
            INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run["session_uid"],
                run["short"],
                run["model"],
                run["model_group"],
                run["session_date"],
                run["dur_min"],
                run["active_min_gap_cap_20"],
                run["tool_calls"],
                run["cbm_calls"],
                run["willow_calls"],
                run["raw_tool_calls"],
                run["semantic_search_calls"],
                run["score_10"],
                int(run["cbm_only_pass"]),
                int(run["field_report"]),
                int(run["ending_exact"]),
                run["concrete_refs"],
                run["output_tokens"],
                run["cache_read_tokens"],
                run["cache_write_tokens"],
                run["path"],
            ),
        )
        for name, count in run["tool_histogram"].items():
            con.execute("INSERT INTO run_tools VALUES (?, ?, ?, 'all')", (run["session_uid"], name, count))
        for name, count in run["cbm_tool_histogram"].items():
            con.execute("INSERT INTO run_tools VALUES (?, ?, ?, 'cbm')", (run["session_uid"], name, count))
        for criterion, passed in run["criteria"].items():
            con.execute("INSERT INTO run_criteria VALUES (?, ?, ?)", (run["session_uid"], criterion, int(passed)))
    for key, value in summary.items():
        con.execute("INSERT INTO summary VALUES (?, ?)", (key, json.dumps(value, ensure_ascii=False)))
    con.commit()
    con.close()


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        by_model[run["model"]].append(run)

    def avg(items: list[dict[str, Any]], key: str) -> float:
        values = [item[key] for item in items if item.get(key) is not None]
        return round(sum(values) / len(values), 3) if values else 0.0

    model_summary = {}
    for model, items in sorted(by_model.items()):
        model_summary[model] = {
            "runs": len(items),
            "avg_score_10": avg(items, "score_10"),
            "avg_cbm_calls": avg(items, "cbm_calls"),
            "cbm_only_pass_rate": round(sum(1 for i in items if i["cbm_only_pass"]) / len(items), 3),
            "field_report_rate": round(sum(1 for i in items if i["field_report"]) / len(items), 3),
            "ending_rate": round(sum(1 for i in items if i["ending_exact"]) / len(items), 3),
            "detect_changes_rate": round(sum(1 for i in items if i["cbm_tool_histogram"].get("detect_changes")) / len(items), 3),
            "semantic_search_total": sum(i["semantic_search_calls"] for i in items),
        }

    aggregate_tools: Counter[str] = Counter()
    for run in runs:
        aggregate_tools.update(run["cbm_tool_histogram"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sidecar_db": str(SIDECAR_DB),
        "canonical_db_mutated": False,
        "prompt_family": "cartographer_code_memory",
        "session_count": len(runs),
        "model_summary": model_summary,
        "totals": {
            "cbm_only_pass": sum(1 for run in runs if run["cbm_only_pass"]),
            "field_report": sum(1 for run in runs if run["field_report"]),
            "ending_exact": sum(1 for run in runs if run["ending_exact"]),
            "willow_violations": sum(1 for run in runs if run["willow_calls"] > 0),
            "raw_tool_violations": sum(1 for run in runs if run["raw_tool_calls"] > 0),
            "detect_changes_used": sum(1 for run in runs if run["cbm_tool_histogram"].get("detect_changes")),
            "semantic_search_calls": sum(run["semantic_search_calls"] for run in runs),
        },
        "aggregate_cbm_tools": dict(sorted(aggregate_tools.items())),
        "scoring": {
            "max_score": 10,
            "criteria": [
                "used_cbm_not_raw",
                "called_get_architecture",
                "called_trace_path_three",
                "used_semantic_search",
                "used_detect_changes",
                "zero_willow_tools",
                "three_concrete_refs",
                "exact_ending",
                "states_uncertainty",
                "danger_justified",
            ],
        },
    }


def cell(value: Any) -> str:
    if value is None:
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(runs: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# Cartographer Code-Memory Benchmark",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "Prompt family: `cartographer_code_memory`",
        "",
        "## Totals",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    for key, value in summary["totals"].items():
        lines.append(f"| {cell(key)} | {cell(value)} |")
    lines.extend(
        [
            "",
            "## Model Summary",
            "",
            "| Model | Runs | Avg Score /10 | Avg CBM Calls | CBM-Only Pass | Ending Pass | Detect Changes | Semantic Calls |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for model, row in summary["model_summary"].items():
        lines.append(
            "| "
            + " | ".join(
                [
                    cell(model),
                    cell(row["runs"]),
                    cell(row["avg_score_10"]),
                    cell(row["avg_cbm_calls"]),
                    cell(row["cbm_only_pass_rate"]),
                    cell(row["ending_rate"]),
                    cell(row["detect_changes_rate"]),
                    cell(row["semantic_search_total"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Runs",
            "",
            "| Short | Model | Score | CBM | Raw | Willow | Semantic | Detect | Refs | Field | Ending | Top CBM Tools |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for run in sorted(runs, key=lambda r: (r["model_group"], r["short"])):
        top = ", ".join(f"{k}({v})" for k, v in Counter(run["cbm_tool_histogram"]).most_common(4))
        lines.append(
            "| "
            + " | ".join(
                [
                    cell(run["short"]),
                    cell(run["model"]),
                    cell(run["score_10"]),
                    cell(run["cbm_calls"]),
                    cell(run["raw_tool_calls"]),
                    cell(run["willow_calls"]),
                    cell(run["semantic_search_calls"]),
                    cell(run["cbm_tool_histogram"].get("detect_changes", 0)),
                    cell(run["concrete_refs"]),
                    cell("yes" if run["field_report"] else "no"),
                    cell("yes" if run["ending_exact"] else "no"),
                    cell(top or "—"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Sonnet and Opus runs used the CBM MCP tools directly and respected the no-Willow boundary.",
            "- Haiku completed the story format but routed tool work through Bash/subagents rather than CBM MCP calls.",
            "- `detect_changes` is the weakest covered objective in this prompt; only one run used it directly.",
            "",
            "## Files",
            "",
            f"- Sidecar DB: `{SIDECAR_DB.name}`",
            f"- JSON report: `{REPORT_JSON.name}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    missing = [sid for sid in SESSIONS if not (PROJECT / f"{sid}.jsonl").exists()]
    if missing:
        raise RuntimeError("missing sessions: " + ", ".join(missing))
    runs = [scan_session(PROJECT / f"{sid}.jsonl") for sid in SESSIONS]
    summary = summarize(runs)
    write_db(runs, summary)
    REPORT_JSON.write_text(
        json.dumps({"summary": summary, "runs": runs}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    REPORT_MD.write_text(render_markdown(runs, summary), encoding="utf-8")
    print(json.dumps({"sidecar_db": str(SIDECAR_DB), "json": str(REPORT_JSON), "markdown": str(REPORT_MD), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
