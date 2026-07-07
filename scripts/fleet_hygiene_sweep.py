#!/usr/bin/env python3
"""
fleet_hygiene_sweep.py — Single entry point for fleet hygiene / audit sweeps.

Read-only by default. Aggregates repo sweeps, hook wiring, hardening scans,
Kart sandbox audit closure, MCP inventory, SAFE path checks, kart-script
retention, and filesystem groom reporting — the scripts agents previously
had to discover piecemeal.

Usage:
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_hygiene_sweep.py
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_hygiene_sweep.py --dry-run --list-phases
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_hygiene_sweep.py --only repos,hooks,hardening
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_hygiene_sweep.py --emit-flags
  WILLOW_AGENT_NAME=willow python3 scripts/fleet_hygiene_sweep.py --apply-kart --apply-groom-t1

Environment:
  WILLOW_HOME — report dir default ~/.willow/reports/
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
    "repos": {
        "title": "Git repo fleet sweep (divergence, litter, untracked)",
        "script": "scripts/repo_fleet_sweep.py",
        "output": "stdout JSON + optional SOIL flags (--emit-flags)",
        "timer": "systemd/repo-fleet-sweep.timer (Mon 04:00)",
    },
    "hooks": {
        "title": "Claude Code hook wiring + loop registry audit",
        "script": "scripts/hook_wiring_audit.py",
        "output": "SOIL flag summary + ~/.claude/settings.json structural check",
        "timer": "systemd/hook-wiring-audit.timer (daily 04:30)",
    },
    "hardening": {
        "title": "Fleet hardening scan (merge conflicts, doc links, CI)",
        "script": "scripts/fleet_hardening_scan.py",
        "output": "finding groups JSON; exit 1 on blocking issues",
    },
    "audit": {
        "title": "Kart sandbox audit definition-of-done harness",
        "script": "scripts/audit_verify.py",
        "output": "S1-S18 gated closure table; exit 1 on regression",
    },
    "mcp": {
        "title": "MCP server inventory (workspace)",
        "script": "scripts/mcp_inventory.py",
        "output": "wired servers + Willow facade verbs for this repo",
    },
    "paths": {
        "title": "SAFE canonical path audit",
        "script": "scripts/audit_safe_paths.py",
        "output": "SAFE_ROOT / agents_root / mcp.json env alignment",
    },
    "kart": {
        "title": "Kart script body retention sweep",
        "script": "scripts/kart_scripts_sweep.py",
        "output": "auto-generated kart_*.py older than --kart-days (dry-run default)",
    },
    "groom": {
        "title": "Filesystem groom pass (handoffs, intake, backups, dispatch)",
        "script": "scripts/filesystem_groom_pass.py",
        "output": "tiered TTL report; apply via --apply-groom-t1/t2",
    },
}

OPTIONAL_MANIFEST: dict[str, str] = {
    "scripts/pii_check.py": "PII gate on git diff (stdin) — use --only pii before PR",
    "scripts/mcp_inventory.py --fleet": "slow ~/github MCP sweep",
    "scripts/check_mcp_registry.py": "registry vs sap/mcp_registry.json drift",
    "scripts/health_report.py": "operator comfort check (manifests, dream, nest)",
    "scripts/verify_public_fallback.py": "public doc fallback links",
    "scripts/fleet_data_repair.py": "Postgres fleet data repair (writes — manual)",
    "scripts/repo_fleet_sweep.py --stash-parity": "stash ↔ KB atom parity (needs Postgres)",
}

DEFAULT_PHASES = tuple(PHASE_MANIFEST.keys())


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None, stdin: str | None = None) -> dict[str, Any]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    proc = subprocess.run(
        cmd,
        cwd=cwd or _REPO,
        capture_output=True,
        text=True,
        env=merged,
        input=stdin,
    )
    return {
        "cmd": " ".join(cmd),
        "rc": proc.returncode,
        "stdout": proc.stdout[-8000:] if proc.stdout else "",
        "stderr": proc.stderr[-4000:] if proc.stderr else "",
    }


def phase_repos(
    *,
    root: Path,
    emit_flags: bool,
    stash_parity: bool,
    dry_run: bool,
) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "repo_fleet_sweep.py"), "--root", str(root), "--json", "--agent", AGENT]
    if emit_flags and not dry_run:
        cmd.append("--emit-flags")
    if stash_parity:
        cmd.append("--stash-parity")
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_hooks(*, emit_flags: bool, dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "hook_wiring_audit.py"), "--agent", AGENT, "--json"]
    if emit_flags and not dry_run:
        cmd.append("--emit-flag")
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_hardening(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "fleet_hardening_scan.py"), "--json"]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_audit(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "audit_verify.py"), "--json"]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_mcp(*, fleet: bool, dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "mcp_inventory.py"), "--json"]
    if fleet:
        cmd.append("--fleet")
    else:
        cmd.extend(["--workspace", str(_REPO)])
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_paths(dry_run: bool) -> dict[str, Any]:
    cmd = [PYTHON, str(_SCRIPTS / "audit_safe_paths.py")]
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_kart(*, apply: bool, kart_days: int, report_days: int, dry_run: bool) -> dict[str, Any]:
    cmd = [
        PYTHON,
        str(_SCRIPTS / "kart_scripts_sweep.py"),
        "--days",
        str(kart_days),
        "--report-days",
        str(report_days),
    ]
    if apply and not dry_run:
        cmd.append("--apply")
    if dry_run:
        return {"dry_run": True, "would_run": cmd}
    return _run(cmd)


def phase_groom(*, apply_t1: bool, apply_t2: bool, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        cmd = [PYTHON, str(_SCRIPTS / "filesystem_groom_pass.py")]
        if apply_t1:
            cmd.append("--apply-t1")
        if apply_t2:
            cmd.append("--apply-t2")
        return {"dry_run": True, "would_run": cmd}
    cmd = [PYTHON, str(_SCRIPTS / "filesystem_groom_pass.py")]
    if apply_t1:
        cmd.append("--apply-t1")
    if apply_t2:
        cmd.append("--apply-t2")
    return _run(cmd)


def phase_pii(*, diff_base: str, dry_run: bool) -> dict[str, Any]:
    diff_cmd = ["git", "-C", str(_REPO), "diff", diff_base]
    if dry_run:
        return {"dry_run": True, "would_run": diff_cmd + ["|", "pii_check.py"]}
    diff_proc = subprocess.run(diff_cmd, capture_output=True, text=True)
    pii_cmd = [PYTHON, str(_SCRIPTS / "pii_check.py")]
    return _run(pii_cmd, stdin=diff_proc.stdout)


def _context_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "root": Path(args.root).expanduser(),
        "emit_flags": args.emit_flags,
        "stash_parity": args.stash_parity,
        "mcp_fleet": args.mcp_fleet,
        "apply_kart": args.apply_kart,
        "kart_days": args.kart_days,
        "report_days": args.report_days,
        "apply_groom_t1": args.apply_groom_t1,
        "apply_groom_t2": args.apply_groom_t2,
        "diff_base": args.diff_base,
        "dry_run": args.dry_run,
    }


PHASE_RUNNERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "repos": lambda ctx: phase_repos(
        root=ctx["root"],
        emit_flags=ctx["emit_flags"],
        stash_parity=ctx["stash_parity"],
        dry_run=ctx["dry_run"],
    ),
    "hooks": lambda ctx: phase_hooks(emit_flags=ctx["emit_flags"], dry_run=ctx["dry_run"]),
    "hardening": lambda ctx: phase_hardening(ctx["dry_run"]),
    "audit": lambda ctx: phase_audit(ctx["dry_run"]),
    "mcp": lambda ctx: phase_mcp(fleet=ctx["mcp_fleet"], dry_run=ctx["dry_run"]),
    "paths": lambda ctx: phase_paths(ctx["dry_run"]),
    "kart": lambda ctx: phase_kart(
        apply=ctx["apply_kart"],
        kart_days=ctx["kart_days"],
        report_days=ctx["report_days"],
        dry_run=ctx["dry_run"],
    ),
    "groom": lambda ctx: phase_groom(
        apply_t1=ctx["apply_groom_t1"],
        apply_t2=ctx["apply_groom_t2"],
        dry_run=ctx["dry_run"],
    ),
    "pii": lambda ctx: phase_pii(diff_base=ctx["diff_base"], dry_run=ctx["dry_run"]),
}


def run_sweep(*, phases: tuple[str, ...], ctx: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "agent": AGENT,
        "dry_run": ctx["dry_run"],
        "github_root": str(ctx["root"]),
        "phases_requested": list(phases),
        "manifest": PHASE_MANIFEST,
        "optional_related": OPTIONAL_MANIFEST,
        "options": {
            "emit_flags": ctx["emit_flags"],
            "stash_parity": ctx["stash_parity"],
            "mcp_fleet": ctx["mcp_fleet"],
            "apply_kart": ctx["apply_kart"],
            "apply_groom_t1": ctx["apply_groom_t1"],
            "apply_groom_t2": ctx["apply_groom_t2"],
        },
        "results": {},
        "failed": [],
    }
    for name in phases:
        if name not in PHASE_RUNNERS:
            report["failed"].append({"phase": name, "error": "unknown phase"})
            continue
        print(f"[hygiene] phase={name} dry_run={ctx['dry_run']}", file=sys.stderr, flush=True)
        result = PHASE_RUNNERS[name](ctx)
        report["results"][name] = result
        rc = result.get("rc", 0 if result.get("dry_run") else 1)
        if rc != 0:
            report["failed"].append({"phase": name, "rc": rc})
    report["ok"] = len(report["failed"]) == 0
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fleet hygiene / audit sweep (single entry point)")
    ap.add_argument(
        "--only",
        default="",
        help=f"Comma-separated phases (default: all). Choices: {','.join(DEFAULT_PHASES)},pii",
    )
    ap.add_argument("--skip", default="", help="Comma-separated phases to skip")
    ap.add_argument("--root", default=str(Path.home() / "github"), help="Git root for repo sweep")
    ap.add_argument("--emit-flags", action="store_true", help="Raise SOIL flags (repos + hooks)")
    ap.add_argument("--stash-parity", action="store_true", help="Include stash↔KB parity in repos phase")
    ap.add_argument("--mcp-fleet", action="store_true", help="Slow ~/github MCP inventory instead of workspace")
    ap.add_argument("--apply-kart", action="store_true", help="Delete stale auto-generated kart_*.py bodies")
    ap.add_argument("--kart-days", type=int, default=14, help="Kart auto-delete age threshold")
    ap.add_argument("--report-days", type=int, default=60, help="Kart named-file report threshold")
    ap.add_argument("--apply-groom-t1", action="store_true", help="Filesystem groom tier-1 deletes")
    ap.add_argument("--apply-groom-t2", action="store_true", help="Filesystem groom tier-2 archive")
    ap.add_argument(
        "--diff-base",
        default="HEAD",
        help="Git ref for optional pii phase (default: HEAD unstaged+staged vs index)",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print what would run without executing")
    ap.add_argument("--list-phases", action="store_true", help="Print phase manifest and exit")
    ap.add_argument(
        "--report",
        default="",
        help="Write JSON report path (default: $WILLOW_HOME/reports/fleet_hygiene_sweep_report.json)",
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_phases:
        payload = {"phases": PHASE_MANIFEST, "optional_related": OPTIONAL_MANIFEST}
        payload["optional_phases"] = {"pii": "scripts/pii_check.py on git diff (--only pii)"}
        print(json.dumps(payload, indent=2))
        return 0

    phases = tuple(p.strip() for p in args.only.split(",") if p.strip()) if args.only else DEFAULT_PHASES
    skip = {p.strip() for p in args.skip.split(",") if p.strip()}
    phases = tuple(p for p in phases if p not in skip)

    ctx = _context_from_args(args)
    report = run_sweep(phases=phases, ctx=ctx)

    reports_dir = willow_home(_REPO) / "reports"
    report_path = Path(args.report).expanduser() if args.report else reports_dir / "fleet_hygiene_sweep_report.json"
    if not args.dry_run:
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)

    print(json.dumps({"ok": report["ok"], "failed": report["failed"], "report": str(report_path)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
