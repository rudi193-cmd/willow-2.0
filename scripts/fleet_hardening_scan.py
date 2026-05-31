#!/usr/bin/env python3
"""Scan for common fleet breakages — run before release or after big merges.

Usage: python3 scripts/fleet_hardening_scan.py [--json]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", "worktrees", "node_modules", ".venv", ".venv-dev", "archive"}


def run(cmd: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def merge_conflicts() -> list[str]:
    hits: list[str] = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or any(part in SKIP_PARTS for part in p.parts):
            continue
        if p.suffix not in {".md", ".py", ".yml", ".yaml", ".json", ".toml", ".sh"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if re.search(r"^<<<<<<<", text, re.M):
            hits.append(str(p.relative_to(ROOT)))
    return hits


def broken_doc_links(limit: int = 30) -> list[str]:
    link_re = re.compile(r"\]\(([^)#]+)\)")
    optional = {"../willow.md", "willow.md"}
    broken: list[str] = []
    for md in (ROOT / "docs").rglob("*.md"):
        text = md.read_text(encoding="utf-8", errors="ignore")
        for m in link_re.finditer(text):
            target = m.group(1)
            if target.startswith(("http", "mailto", "#")):
                continue
            if target in optional or target.endswith("/willow.md"):
                continue
            tp = (md.parent / target).resolve()
            if tp.exists():
                continue
            # Repo-root relative (e.g. docs/CONTRACT.md -> AGENTS.md)
            root_tp = (ROOT / target).resolve()
            if root_tp.exists():
                continue
            broken.append(f"{md.relative_to(ROOT)} -> {target}")
            if len(broken) >= limit:
                return broken
    return broken


def main() -> int:
    findings: list[dict] = []

    conflicts = merge_conflicts()
    if conflicts:
        findings.append({"cat": "merge_conflict", "items": conflicts})

    if (ROOT / "issue_body.md").exists():
        findings.append({"cat": "leftover_file", "path": "issue_body.md"})

    r = run(["python3", "-m", "pytest", "--collect-only", "-q"])
    if r.returncode != 0:
        findings.append({"cat": "pytest_collect", "detail": (r.stderr or r.stdout)[-1000:]})

    r = run(["bash", "scripts/lint_first_party.sh"])
    if r.returncode != 0:
        findings.append({"cat": "ruff", "detail": (r.stdout + r.stderr)[-800:]})

    r = run(["./willow.sh", "verify"])
    verify_out = r.stdout + r.stderr
    bad = [ln.strip() for ln in verify_out.splitlines() if "BAD SIG" in ln or " FAIL" in ln]
    if bad or r.returncode != 0:
        # BAD SIG needs operator GPG — warn, do not block release scan on sandbox-only runs
        gpg_only = bad and all("BAD SIG" in ln or "MISSING SIG" in ln for ln in bad)
        findings.append(
            {
                "cat": "willow_verify",
                "lines": bad[:10],
                "rc": r.returncode,
                "operator_action": gpg_only and "Run sync_safe_agent_manifests.py with GPG on host",
            }
        )

    broken = broken_doc_links()
    if broken:
        findings.append({"cat": "broken_doc_links", "count": len(broken), "sample": broken[:15]})

    r = run(["gh", "pr", "list", "--repo", "rudi193-cmd/willow-2.0", "--state", "open", "--json", "number,title,statusCheckRollup"])
    if r.returncode == 0:
        for pr in json.loads(r.stdout):
            failed = [
                c.get("name")
                for c in (pr.get("statusCheckRollup") or [])
                if c.get("conclusion") == "FAILURE"
            ]
            if failed:
                findings.append({"cat": "pr_ci_fail", "pr": pr["number"], "checks": failed})

    r = run(["git", "status", "--porcelain", "scripts/"])
    if r.stdout.strip():
        findings.append({"cat": "scripts_untracked", "detail": r.stdout.strip()})

    report = {"root": str(ROOT), "finding_groups": len(findings), "findings": findings}
    blocking = [f for f in findings if f.get("cat") not in {"willow_verify", "scripts_untracked"}]
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print(f"Fleet hardening scan — {len(findings)} issue group(s)")
        for f in findings:
            print(f"  [{f['cat']}]", json.dumps({k: v for k, v in f.items() if k != "cat"})[:200])
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
