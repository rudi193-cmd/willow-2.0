#!/usr/bin/env python3
"""
fleet_witness_sweep.py — Single entry point for weekly SLI / trust witnesses.

Aggregates WCE continuity eval, W8 census, retrieval gold, LoCoMo pilot, and
CI smoke scorecard — evaluation science separate from session ingest.

Usage:
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_witness_sweep.py
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_witness_sweep.py --only retrieval,wce
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_witness_sweep.py --force
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_witness_sweep.py --only locomo --dry-run
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
    "retrieval": {
        "title": "Fleet retrieval gold gate",
        "script": "scripts/retrieval_gold_check.py",
        "output": "pass_ratio vs willow/bench/scorecard.json",
    },
    "wce": {
        "title": "Willow Continuity Eval weekly witness",
        "script": "scripts/wce_witness.py",
        "output": "willow/bench/continuity/runs/wce_*.json",
        "timer": "systemd/willow-wce.timer (weekly)",
    },
    "w8": {
        "title": "W8 canonical-reconstruction census witness",
        "script": "scripts/w8_census_witness.py",
        "output": "sandbox/stone_soup/reports/recon-canonical.json",
        "timer": "systemd/willow-w8-census.timer (weekly)",
    },
    "locomo": {
        "title": "LoCoMo Path A external-memory pilot",
        "script": "willow/bench/locomo/path_a_locomo_pilot.py",
        "output": "recall@k / MRR vs baseline",
    },
    "smoke": {
        "title": "CI smoke scorecard (pytest + retrieval)",
        "script": "scripts/smoke_scorecard.sh",
        "output": "full test suite + retrieval gold",
    },
}

OPTIONAL_MANIFEST: dict[str, str] = {
    "willow/bench/continuity/run_wce.py": "low-level WCE runner (wce_witness wraps this)",
    "willow/bench/continuity/mine_wce_queries.py": "WCE query mining",
    "willow/bench/retrieval_gold_ci.py": "CI wrapper for retrieval gold",
}

DEFAULT_PHASES = ("retrieval", "wce", "w8")


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


def phase_retrieval(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "retrieval_gold_check.py")]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_wce(*, dry_run: bool, force: bool, pair_limit: int) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "wce_witness.py"), "--agent", AGENT]
    if force:
        cmd.append("--force")
    else:
        cmd.append("--check-first")
    if pair_limit:
        cmd.extend(["--pair-limit", str(pair_limit)])
    if dry_run:
        cmd.append("--dry-run")
    if dry_run and not force:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_w8(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "w8_census_witness.py")]
    if dry_run:
        cmd.append("--dry-run")
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_locomo(*, dry_run: bool, semantic: bool, conv_index: int | None) -> dict[str, Any]:
    script = _REPO / "willow" / "bench" / "locomo" / "path_a_locomo_pilot.py"
    cmd = [PYTHON, str(script)]
    if conv_index is not None:
        cmd.extend(["--conv-index", str(conv_index)])
    else:
        cmd.append("--all")
    if semantic:
        cmd.append("--semantic")
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_smoke(dry_run: bool) -> dict[str, Any]:
    script = _SCRIPTS / "smoke_scorecard.sh"
    cmd = ["bash", str(script)]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


PHASE_RUNNERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "retrieval": lambda ctx: phase_retrieval(ctx["dry_run"]),
    "wce": lambda ctx: phase_wce(
        dry_run=ctx["dry_run"], force=ctx["force"], pair_limit=ctx["pair_limit"]
    ),
    "w8": lambda ctx: phase_w8(ctx["dry_run"]),
    "locomo": lambda ctx: phase_locomo(
        dry_run=ctx["dry_run"],
        semantic=ctx["locomo_semantic"],
        conv_index=ctx["locomo_conv_index"],
    ),
    "smoke": lambda ctx: phase_smoke(ctx["dry_run"]),
}


def run_sweep(*, phases: tuple[str, ...], ctx: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "agent": AGENT,
        "dry_run": ctx["dry_run"],
        "force": ctx["force"],
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
        print(f"[witness] phase={name} dry_run={ctx['dry_run']}", file=sys.stderr, flush=True)
        result = PHASE_RUNNERS[name](ctx)
        report["results"][name] = result
        rc = result.get("rc", 0 if result.get("dry_run") else 1)
        if rc != 0:
            report["failed"].append({"phase": name, "rc": rc})
    report["ok"] = len(report["failed"]) == 0
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fleet witness / SLI sweep")
    ap.add_argument(
        "--only",
        default="",
        help=f"Comma-separated phases (default: retrieval,wce,w8). Choices: {','.join(PHASE_MANIFEST)}",
    )
    ap.add_argument("--skip", default="", help="Comma-separated phases to skip")
    ap.add_argument("--force", action="store_true", help="Run WCE even if interval not elapsed")
    ap.add_argument("--pair-limit", type=int, default=0, help="WCE handoff pair cap (0=all)")
    ap.add_argument("--locomo-conv", type=int, default=-1, help="LoCoMo single conv index (default: --all)")
    ap.add_argument("--no-locomo-semantic", action="store_true", help="LoCoMo without --semantic")
    ap.add_argument("--dry-run", action="store_true", help="Print/would-run only")
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
        "force": args.force,
        "pair_limit": args.pair_limit,
        "locomo_semantic": not args.no_locomo_semantic,
        "locomo_conv_index": args.locomo_conv if args.locomo_conv >= 0 else None,
    }
    report = run_sweep(phases=phases, ctx=ctx)

    reports_dir = willow_home(_REPO) / "reports"
    report_path = Path(args.report).expanduser() if args.report else reports_dir / "fleet_witness_sweep_report.json"
    if not args.dry_run:
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)

    print(json.dumps({"ok": report["ok"], "failed": report["failed"], "report": str(report_path)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
