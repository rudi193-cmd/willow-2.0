#!/usr/bin/env python3
"""
fleet_metabolic_sweep.py — Single entry point for nightly fleet metabolism (Norn pass).

Wraps run_norn.py / core.metabolic.norn_pass and optional sibling passes that
norn does not call: sleep consolidation, correction promote, session quality.

Usage:
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_metabolic_sweep.py
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_metabolic_sweep.py --dry-run --list-phases
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_metabolic_sweep.py --only norn,sleep
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_SCRIPTS))

from core.agent_identity import require_agent_name
from willow.fylgja.willow_home import willow_home

AGENT = require_agent_name()
PYTHON = sys.executable

PHASE_MANIFEST: dict[str, dict[str, str]] = {
    "norn": {
        "title": "Norn / metabolic pass (compost, signals, intake, groom schedule)",
        "script": "scripts/run_norn.py",
        "output": "norn JSON report; queues dream/WCE when due",
        "timer": "systemd/willow-metabolic.timer (daily)",
    },
    "sleep": {
        "title": "KB sleep consolidation (NREM dedup, contradictions, SQLite→PG)",
        "script": "scripts/sleep_consolidation.py",
        "output": "invalid_at on duplicates; frank_ledger contradictions",
    },
    "corrections": {
        "title": "Promote recurring corrections to KB",
        "script": "scripts/promote_corrections.py",
        "output": "Postgres knowledge (category=correction)",
    },
    "quality": {
        "title": "Session quality scorer",
        "script": "scripts/session_quality_scorer.py",
        "output": "$WILLOW_HOME/session_quality_report.json",
    },
    "gaps": {
        "title": "Cross-session topic gap detector",
        "script": "scripts/cross_session_gap_detector.py",
        "output": "$WILLOW_HOME/session_gaps.json",
    },
}

OPTIONAL_MANIFEST: dict[str, str] = {
    "scripts/promote_signals.py": "also inside norn pass — standalone re-run",
    "scripts/signal_recurrence_tracker.py": "also inside norn pass",
    "scripts/filesystem_groom_pass.py": "also inside norn pass (end of norn)",
    "scripts/promote_intake.py --fleet": "also inside norn pass",
    "core/metabolic.py": "full norn_pass source — compost, intelligence, signals",
}

DEFAULT_PHASES = ("norn",)


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
        "stdout": proc.stdout[-12000:] if proc.stdout else "",
        "stderr": proc.stderr[-4000:] if proc.stderr else "",
    }


def phase_norn(*, dry_run: bool, collections: list[str]) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "run_norn.py")]
    if dry_run:
        cmd.append("--dry-run")
    if collections:
        cmd.extend(["--collections", *collections])
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_sleep(*, dry_run: bool, skip_intelligence: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "sleep_consolidation.py")]
    if dry_run:
        cmd.append("--dry-run")
    if skip_intelligence:
        cmd.append("--skip-intelligence")
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_corrections(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "promote_corrections.py")]
    if dry_run:
        cmd.append("--dry-run")
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_quality(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "session_quality_scorer.py")]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_gaps(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "cross_session_gap_detector.py")]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


PHASE_RUNNERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "norn": lambda ctx: phase_norn(dry_run=ctx["dry_run"], collections=ctx["collections"]),
    "sleep": lambda ctx: phase_sleep(dry_run=ctx["dry_run"], skip_intelligence=ctx["skip_intelligence"]),
    "corrections": lambda ctx: phase_corrections(ctx["dry_run"]),
    "quality": lambda ctx: phase_quality(ctx["dry_run"]),
    "gaps": lambda ctx: phase_gaps(ctx["dry_run"]),
}


def run_sweep(*, phases: tuple[str, ...], ctx: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "agent": AGENT,
        "dry_run": ctx["dry_run"],
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
        print(f"[metabolic] phase={name} dry_run={ctx['dry_run']}", file=sys.stderr, flush=True)
        result = PHASE_RUNNERS[name](ctx)
        report["results"][name] = result
        rc = result.get("rc", 0 if result.get("dry_run") else 1)
        if rc != 0:
            report["failed"].append({"phase": name, "rc": rc})
    report["ok"] = len(report["failed"]) == 0
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fleet metabolic / Norn sweep")
    ap.add_argument(
        "--only",
        default="",
        help=f"Comma-separated phases (default: norn). Choices: {','.join(PHASE_MANIFEST)}",
    )
    ap.add_argument("--skip", default="", help="Comma-separated phases to skip")
    ap.add_argument(
        "--collections",
        nargs="*",
        default=[],
        help="SOIL collection globs for norn reflection pass",
    )
    ap.add_argument("--skip-intelligence", action="store_true", help="sleep phase: skip insight/chunk passes")
    ap.add_argument("--dry-run", action="store_true", help="No writes (norn + sleep + corrections)")
    ap.add_argument("--list-phases", action="store_true", help="Print manifest and exit")
    ap.add_argument("--report", default="", help="JSON report path")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_phases:
        print(json.dumps({"phases": PHASE_MANIFEST, "optional_related": OPTIONAL_MANIFEST}, indent=2))
        return 0

    phases = tuple(p.strip() for p in args.only.split(",") if p.strip()) if args.only else DEFAULT_PHASES
    skip = {p.strip() for p in args.skip.split(",") if p.strip()}
    phases = tuple(p for p in phases if p not in skip)

    ctx = {
        "dry_run": args.dry_run,
        "collections": args.collections,
        "skip_intelligence": args.skip_intelligence,
    }
    report = run_sweep(phases=phases, ctx=ctx)

    reports_dir = willow_home(_REPO) / "reports"
    report_path = Path(args.report).expanduser() if args.report else reports_dir / "fleet_metabolic_sweep_report.json"
    if not args.dry_run:
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)

    print(json.dumps({"ok": report["ok"], "failed": report["failed"], "report": str(report_path)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
