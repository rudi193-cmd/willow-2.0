#!/usr/bin/env python3
"""
fleet_kb_ship_sweep.py — Single entry point for KB ship-shape gates before merge/release.

Read-only by default. Combines preflight, embedding completeness, bitemporal audit,
retrieval gold, dry-run repairs, and optional embed/repair apply passes.

Usage:
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_kb_ship_sweep.py
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_kb_ship_sweep.py --dry-run --list-phases
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_kb_ship_sweep.py --apply-embed --embed-limit 500
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
    "preflight": {
        "title": "KB ship-shape preflight (graph, embeddings, human queue)",
        "script": "scripts/kb_preflight.py",
        "output": "PASS/WARN/FAIL JSON report",
    },
    "completeness": {
        "title": "Postgres embedding completeness gate",
        "script": "scripts/pg_completeness_gate.py",
        "output": "≥ threshold %% on knowledge/jeles/opus",
    },
    "bitemporal": {
        "title": "Bi-temporal supersede-not-delete audit",
        "script": "scripts/audit_bitemporal.py",
        "output": "violation counts; exit 1 if any",
    },
    "retrieval": {
        "title": "Retrieval gold regression gate",
        "script": "scripts/retrieval_gold_check.py",
        "output": "pass_ratio vs scorecard baseline",
    },
    "repair_dangling": {
        "title": "KB repair — dangling edges (dry-run default)",
        "script": "scripts/kb_repair.py delete-dangling",
        "output": "edges with missing endpoints",
    },
    "repair_dedup_title": {
        "title": "KB repair — duplicate title disambiguation (dry-run default)",
        "script": "scripts/kb_repair.py dedup-title",
        "output": "proposed renames",
    },
    "embed": {
        "title": "Embedding backfill for NULL vectors",
        "script": "scripts/willow_embed_backfill.py",
        "output": "knowledge/opus/jeles embeddings",
    },
}

OPTIONAL_MANIFEST: dict[str, str] = {
    "scripts/kb_repair.py dedup-exact": "exact duplicate merge — requires --apply --consent",
    "scripts/kb_repair.py anchor-low-degree": "bridge orphan atoms — requires --apply --consent",
    "scripts/repair_bitemporal.py": "fix bitemporal violations — --apply writes + FRANK",
    "scripts/binder_backfill_postgres_edges.py": "binder_edges → public.edges sync",
    "scripts/fleet_data_repair.py": "fleet-wide Postgres repair (manual)",
}

DEFAULT_PHASES = (
    "preflight",
    "completeness",
    "bitemporal",
    "retrieval",
    "repair_dangling",
    "repair_dedup_title",
)


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


def phase_preflight(threshold: float, dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "kb_preflight.py"), "--threshold", str(threshold), "--json-only"]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_completeness(threshold: float, dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "pg_completeness_gate.py"), "--threshold", str(threshold)]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_bitemporal(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "audit_bitemporal.py")]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_retrieval(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "retrieval_gold_check.py")]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_repair(subcmd: str, *, apply: bool, consent: bool, dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "kb_repair.py"), subcmd]
    if apply and not dry_run:
        cmd.append("--apply")
    if consent and apply:
        cmd.append("--consent")
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_embed(*, apply: bool, limit: int, dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "willow_embed_backfill.py")]
    if not apply or dry_run:
        cmd.append("--dry-run")
    if limit:
        cmd.extend(["--limit", str(limit)])
    if dry_run and not apply:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_binder_edges(*, apply: bool, limit: int, dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "binder_backfill_postgres_edges.py"), "--limit", str(limit)]
    if dry_run or not apply:
        return {"dry_run": True, "would_run": cmd, "note": "writes only with --apply-binder"}
    return _run(cmd)


def phase_bitemporal_repair(*, apply: bool, dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "repair_bitemporal.py")]
    if apply and not dry_run:
        cmd.append("--apply")
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


PHASE_RUNNERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "preflight": lambda ctx: phase_preflight(ctx["threshold"], ctx["dry_run"]),
    "completeness": lambda ctx: phase_completeness(ctx["threshold"], ctx["dry_run"]),
    "bitemporal": lambda ctx: phase_bitemporal(ctx["dry_run"]),
    "retrieval": lambda ctx: phase_retrieval(ctx["dry_run"]),
    "repair_dangling": lambda ctx: phase_repair(
        "delete-dangling", apply=ctx["apply_repair"], consent=ctx["consent"], dry_run=ctx["dry_run"]
    ),
    "repair_dedup_title": lambda ctx: phase_repair(
        "dedup-title", apply=ctx["apply_repair"], consent=ctx["consent"], dry_run=ctx["dry_run"]
    ),
    "embed": lambda ctx: phase_embed(apply=ctx["apply_embed"], limit=ctx["embed_limit"], dry_run=ctx["dry_run"]),
    "binder_edges": lambda ctx: phase_binder_edges(
        apply=ctx["apply_binder"], limit=ctx["binder_limit"], dry_run=ctx["dry_run"]
    ),
    "bitemporal_repair": lambda ctx: phase_bitemporal_repair(
        apply=ctx["apply_bitemporal"], dry_run=ctx["dry_run"]
    ),
}


def run_sweep(*, phases: tuple[str, ...], ctx: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "agent": AGENT,
        "dry_run": ctx["dry_run"],
        "phases_requested": list(phases),
        "manifest": PHASE_MANIFEST,
        "optional_related": OPTIONAL_MANIFEST,
        "options": {
            "threshold": ctx["threshold"],
            "apply_repair": ctx["apply_repair"],
            "apply_embed": ctx["apply_embed"],
            "apply_binder": ctx["apply_binder"],
            "apply_bitemporal": ctx["apply_bitemporal"],
            "consent": ctx["consent"],
        },
        "results": {},
        "failed": [],
    }
    for name in phases:
        if name not in PHASE_RUNNERS:
            report["failed"].append({"phase": name, "error": "unknown phase"})
            continue
        print(f"[kb-ship] phase={name} dry_run={ctx['dry_run']}", file=sys.stderr, flush=True)
        result = PHASE_RUNNERS[name](ctx)
        report["results"][name] = result
        rc = result.get("rc", 0 if result.get("dry_run") else 1)
        if rc != 0:
            report["failed"].append({"phase": name, "rc": rc})
    report["ok"] = len(report["failed"]) == 0
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    all_phases = list(PHASE_MANIFEST) + ["binder_edges", "bitemporal_repair"]
    ap = argparse.ArgumentParser(description="Fleet KB ship-shape sweep")
    ap.add_argument("--only", default="", help=f"Comma-separated phases (default: all). Choices: {','.join(all_phases)}")
    ap.add_argument("--skip", default="", help="Comma-separated phases to skip")
    ap.add_argument("--threshold", type=float, default=96.0, help="Embedding completeness %% gate")
    ap.add_argument("--apply-repair", action="store_true", help="Apply kb_repair subcommands")
    ap.add_argument("--apply-embed", action="store_true", help="Run embed backfill (not dry-run)")
    ap.add_argument("--embed-limit", type=int, default=0, help="Max rows per table for embed phase")
    ap.add_argument("--apply-binder", action="store_true", help="Run binder_edges backfill (writes)")
    ap.add_argument("--binder-limit", type=int, default=500, help="Max binder edges to sync")
    ap.add_argument("--apply-bitemporal", action="store_true", help="Run repair_bitemporal --apply")
    ap.add_argument("--consent", action="store_true", help="Operator consent for edge-writing repairs")
    ap.add_argument("--dry-run", action="store_true", help="Print would-run only")
    ap.add_argument("--list-phases", action="store_true", help="Print manifest and exit")
    ap.add_argument("--report", default="", help="JSON report path")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_phases:
        payload = {
            "phases": PHASE_MANIFEST,
            "optional_phases": {
                "binder_edges": "scripts/binder_backfill_postgres_edges.py (--apply-binder)",
                "bitemporal_repair": "scripts/repair_bitemporal.py (--apply-bitemporal)",
            },
            "optional_related": OPTIONAL_MANIFEST,
        }
        print(json.dumps(payload, indent=2))
        return 0

    phases = tuple(p.strip() for p in args.only.split(",") if p.strip()) if args.only else DEFAULT_PHASES
    skip = {p.strip() for p in args.skip.split(",") if p.strip()}
    phases = tuple(p for p in phases if p not in skip)

    ctx = {
        "dry_run": args.dry_run,
        "threshold": args.threshold,
        "apply_repair": args.apply_repair,
        "apply_embed": args.apply_embed,
        "embed_limit": args.embed_limit,
        "apply_binder": args.apply_binder,
        "binder_limit": args.binder_limit,
        "apply_bitemporal": args.apply_bitemporal,
        "consent": args.consent or os.environ.get("WILLOW_HUMAN_CONSENT") == "1",
    }
    report = run_sweep(phases=phases, ctx=ctx)

    reports_dir = willow_home(_REPO) / "reports"
    report_path = Path(args.report).expanduser() if args.report else reports_dir / "fleet_kb_ship_sweep_report.json"
    if not args.dry_run:
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)

    print(json.dumps({"ok": report["ok"], "failed": report["failed"], "report": str(report_path)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
