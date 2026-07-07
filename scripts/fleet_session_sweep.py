#!/usr/bin/env python3
"""
fleet_session_sweep.py — Single entry point for the full fleet session memory + benchmark pipeline.

Runs every layer agents previously had to discover piecemeal:
  Postgres memory tracker, Jeles registry, cross-runtime bridge, atom extraction,
  KB promotion, Nest benchmark harness, Sonnet 5 cohort, SLI retrieval gold.

Usage:
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_session_sweep.py
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_session_sweep.py --since 2026-07-03
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_session_sweep.py --dry-run --list-phases
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_session_sweep.py --only index,jeles,benchmark,sonnet5,fold,analyze

Environment:
  NEST — benchmark harness dir (default: ~/Desktop/Nest)
  WILLOW_20_DB — atom staging SQLite (default: ~/.willow/willow-2.0.db)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_SCRIPTS))

from core.agent_identity import require_agent_name
from fleet_repos import discover_jsonl_paths, nest_dir

AGENT = require_agent_name()
PYTHON = sys.executable

# Complete inventory — every script in the pipeline (nothing else should be ad-hoc).
PHASE_MANIFEST: dict[str, dict[str, str]] = {
    "index": {
        "title": "Postgres session index fill",
        "script": "scripts/session_indexer.py",
        "output": "public.session_index, public.session_messages → session_query MCP",
    },
    "jeles": {
        "title": "Jeles session registry",
        "script": "scripts/register_jeles_sessions.py",
        "output": "Postgres jeles_sessions",
    },
    "bridge": {
        "title": "Cross-runtime handoff bridge",
        "script": "scripts/bridge_cross_runtime.py",
        "output": "$WILLOW_HOME/handoffs/cross-runtime.json",
    },
    "atoms": {
        "title": "Session atom extraction (SQLite staging)",
        "script": "scripts/extract_atoms_from_sessions.py",
        "output": "$WILLOW_20_DB records (semantic/user/metadata atoms)",
    },
    "promote": {
        "title": "Promote high-confidence atoms to KB",
        "script": "scripts/promote_candidates.py",
        "output": "Postgres knowledge (source_type=session_promote)",
    },
    "intake": {
        "title": "Fleet intake promote (norn-pass)",
        "script": "scripts/promote_intake.py",
        "output": "intake JSONL → KB tiers",
    },
    "edges": {
        "title": "Propose KB edges from atoms",
        "script": "scripts/propose_edges.py",
        "output": "proposed edges JSON (not auto-applied)",
    },
    "handoff": {
        "title": "Handoff index rebuild",
        "script": "sap/tools/build_handoff_db.py",
        "output": "handoffs.db index",
    },
    "benchmark": {
        "title": "Nest benchmark DB ingest (tokens, tools, efficiency)",
        "script": "$NEST/parse_benchmark_sessions.py",
        "output": "$NEST/claude_benchmarks.db",
    },
    "sonnet5": {
        "title": "Sonnet 5 + Cursor Composer cohort normalizer",
        "script": "$NEST/normalize_sonnet5_sessions.py",
        "output": "$NEST/sonnet5_selected_sessions.json",
    },
    "fold": {
        "title": "Fold PR outcomes + comparison chart",
        "script": "$NEST/fold_pr_outcomes.py",
        "output": "$NEST/benchmark_sessions_full.md",
    },
    "analyze": {
        "title": "Benchmark pattern analysis",
        "script": "$NEST/benchmark_analyze.py",
        "output": "$NEST/benchmark_analysis_report.json",
    },
    "sli": {
        "title": "SLI retrieval gold gate (Willow improvement smoke)",
        "script": "scripts/retrieval_gold_check.py",
        "output": "pass_ratio vs willow/bench/scorecard.json baseline",
    },
}

# Related scripts NOT in default sweep (weekly / sidecar / manual — see skill reference).
OPTIONAL_MANIFEST: dict[str, str] = {
    "normalize_fable_sessions.py": "$NEST — Fable 5 sidecar cohort (Jun 2026 field report)",
    "normalize_sonnet46_sessions.py": "$NEST — Sonnet 4.6 cohort sidecar",
    "normalize_recent_model_sessions.py": "$NEST — Opus/Fable/Sonnet recent sidecar",
    "extract_claude_config_stats.py": "$NEST — /config screenshot token stats",
    "benchmarks/sidecars/cartographer_code_memory/normalize_cartographer_code_memory_sessions.py": "controlled CBM prompt bench",
    "willow/bench/locomo/path_a_locomo_pilot.py": "weekly SLI — external memory",
    "willow/bench/continuity/run_wce.py": "weekly SLI — handoff continuity",
    "scripts/smoke_scorecard.sh": "PR smoke — pytest + retrieval gold",
    "scripts/sleep_consolidation.py": "indexed_confidence decay on session_index",
    "scripts/session_correction_extractor.py": "correction atoms from sessions",
    "scripts/session_quality_scorer.py": "session quality heuristics",
    "scripts/cross_session_gap_detector.py": "gap detection across sessions",
    "scripts/index_session_prompts.py": "prompt index pass",
    "scripts/build_claude_sessions_db.py": "legacy claude sessions DB builder",
}

DEFAULT_PHASES = tuple(PHASE_MANIFEST.keys())


def _days_since(since: date) -> int:
    delta = datetime.now(timezone.utc).date() - since
    return max(1, delta.days + 1)


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> dict[str, Any]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    proc = subprocess.run(
        cmd,
        cwd=cwd or _REPO,
        capture_output=True,
        text=True,
        env=merged,
    )
    return {
        "cmd": " ".join(cmd),
        "rc": proc.returncode,
        "stdout": proc.stdout[-8000:] if proc.stdout else "",
        "stderr": proc.stderr[-4000:] if proc.stderr else "",
    }


def phase_index(since: date, dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "session_indexer.py"), "--fleet", "--since", since.isoformat()]
    if dry_run:
        paths = discover_jsonl_paths(since=since)
        return {"dry_run": True, "jsonl_count": len(paths), "would_run": cmd}
    return _run(cmd)


def phase_jeles(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "register_jeles_sessions.py")]
    if dry_run:
        cmd.append("--dry-run")
    return _run(cmd)


def phase_bridge(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "bridge_cross_runtime.py"), "--agent", AGENT]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_atoms(since: date, dry_run: bool) -> dict[str, Any]:
    cmd = [
        PYTHON,
        str(_SCRIPTS / "extract_atoms_from_sessions.py"),
        "--fleet",
        "--since",
        since.isoformat(),
        "--recursive",
    ]
    if not dry_run:
        cmd.append("--write")
    else:
        return {"dry_run": True, "would_run": cmd + ["--write"]}
    return _run(cmd)


def phase_promote(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "promote_candidates.py")]
    if dry_run:
        cmd.append("--dry-run")
    return _run(cmd)


def phase_intake(since: date, dry_run: bool) -> dict[str, Any]:
    days = _days_since(since)
    cmd = [
        PYTHON,
        str(_SCRIPTS / "promote_intake.py"),
        "--fleet",
        "--no-llm",
        "--days",
        str(days),
    ]
    if dry_run:
        cmd.append("--dry-run")
    return _run(cmd)


def phase_edges(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "propose_edges.py"), "propose"]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_handoff(dry_run: bool) -> dict[str, Any]:
    script = _REPO / "sap" / "tools" / "build_handoff_db.py"
    cmd = [PYTHON, str(script)]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_benchmark(since: date, nest: Path, dry_run: bool) -> dict[str, Any]:
    db = nest / "claude_benchmarks.db"
    cmd = [
        PYTHON,
        str(nest / "parse_benchmark_sessions.py"),
        "--db",
        str(db),
        "--since",
        since.isoformat(),
        "--scan-fleet",
        "--summary-only",
    ]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd, cwd=nest)


def phase_sonnet5(since: date, nest: Path, dry_run: bool) -> dict[str, Any]:
    cmd = [
        PYTHON,
        str(nest / "normalize_sonnet5_sessions.py"),
        "--since",
        since.isoformat(),
    ]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd, cwd=nest)


def phase_fold(nest: Path, dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(nest / "fold_pr_outcomes.py")]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd, cwd=nest)


def phase_analyze(nest: Path, dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(nest / "benchmark_analyze.py")]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd, cwd=nest)


def phase_sli(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "retrieval_gold_check.py")]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


PHASE_RUNNERS: dict[str, Callable[..., dict[str, Any]]] = {
    "index": lambda since, nest, dry: phase_index(since, dry),
    "jeles": lambda since, nest, dry: phase_jeles(dry),
    "bridge": lambda since, nest, dry: phase_bridge(dry),
    "atoms": lambda since, nest, dry: phase_atoms(since, dry),
    "promote": lambda since, nest, dry: phase_promote(dry),
    "intake": lambda since, nest, dry: phase_intake(since, dry),
    "edges": lambda since, nest, dry: phase_edges(dry),
    "handoff": lambda since, nest, dry: phase_handoff(dry),
    "benchmark": lambda since, nest, dry: phase_benchmark(since, nest, dry),
    "sonnet5": lambda since, nest, dry: phase_sonnet5(since, nest, dry),
    "fold": lambda since, nest, dry: phase_fold(nest, dry),
    "analyze": lambda since, nest, dry: phase_analyze(nest, dry),
    "sli": lambda since, nest, dry: phase_sli(dry),
}


def run_sweep(
    *,
    since: date,
    phases: tuple[str, ...],
    nest: Path,
    dry_run: bool,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "agent": AGENT,
        "since": since.isoformat(),
        "nest": str(nest),
        "dry_run": dry_run,
        "phases_requested": list(phases),
        "manifest": PHASE_MANIFEST,
        "optional_related": OPTIONAL_MANIFEST,
        "results": {},
        "failed": [],
    }
    for name in phases:
        if name not in PHASE_RUNNERS:
            report["failed"].append({"phase": name, "error": "unknown phase"})
            continue
        print(f"[sweep] phase={name} since={since} dry_run={dry_run}", file=sys.stderr, flush=True)
        result = PHASE_RUNNERS[name](since, nest, dry_run)
        report["results"][name] = result
        rc = result.get("rc", 0 if result.get("dry_run") else 1)
        if rc != 0:
            report["failed"].append({"phase": name, "rc": rc})
    report["ok"] = len(report["failed"]) == 0
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fleet session memory + benchmark sweep (single entry point)")
    ap.add_argument("--since", default="2026-07-03", metavar="YYYY-MM-DD", help="Process sessions from this date")
    ap.add_argument(
        "--only",
        default="",
        help=f"Comma-separated phases (default: all). Choices: {','.join(DEFAULT_PHASES)}",
    )
    ap.add_argument("--skip", default="", help="Comma-separated phases to skip")
    ap.add_argument("--nest", default="", help="Nest benchmark dir (default: $NEST or ~/Desktop/Nest)")
    ap.add_argument("--dry-run", action="store_true", help="Print what would run without writing")
    ap.add_argument("--list-phases", action="store_true", help="Print phase manifest and exit")
    ap.add_argument(
        "--report",
        default="",
        help="Write JSON report path (default: $NEST/fleet_session_sweep_report.json)",
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_phases:
        print(json.dumps({"phases": PHASE_MANIFEST, "optional_related": OPTIONAL_MANIFEST}, indent=2))
        return 0

    since = date.fromisoformat(args.since)
    nest = Path(args.nest).expanduser() if args.nest else nest_dir()
    if not nest.is_dir():
        print(f"NEST dir not found: {nest}", file=sys.stderr)
        return 1

    phases = tuple(p.strip() for p in args.only.split(",") if p.strip()) if args.only else DEFAULT_PHASES
    skip = {p.strip() for p in args.skip.split(",") if p.strip()}
    phases = tuple(p for p in phases if p not in skip)

    report = run_sweep(since=since, phases=phases, nest=nest, dry_run=args.dry_run)
    report_path = Path(args.report).expanduser() if args.report else nest / "fleet_session_sweep_report.json"
    if not args.dry_run:
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)

    print(json.dumps({"ok": report["ok"], "failed": report["failed"], "report": str(report_path)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
