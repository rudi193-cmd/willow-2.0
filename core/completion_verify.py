"""Evidence-gated task completion — VERIFIED / UNVERIFIED.

Borrowed from palios-taey/claude-code-fleet-orchestrator
(`evidence_verification.py` + `completion_guard.py`), transplanted onto Willow's
existing rails: `gh`-via-Kart for the GitHub check, `dispatch_tasks.from_agent`/
`to_agent` for the supervisor/worker relationship (Willow already has explicit
columns — no name-suffix parsing needed).

This module is pure: `verify_completion_evidence` takes an injectable `gh` caller
so it is fully unit-testable offline (same provider-seam trick as
`core/web_search.py`). Slice 2 wires it into `agent_dispatch_result` + the FRANK
ledger; the wiring lives in `sap/sap_mcp.py`, nothing here mutates state.

Config seam (slice 2): the required-checks set, the allowlisted repos, and the
enforcement flag are all env-overridable so the gate can ship default-off and be
tightened per-deployment without a code change. Env is read at call time, so the
defaults below remain the pinned public surface the tests iterate over.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any, Callable

log = logging.getLogger("willow.completion")

# Required CI checks a commit must pass for VERIFIED provenance — the exact gate
# the operator watches by hand on every willow-2.0 PR. Override per-deployment
# with WILLOW_COMPLETION_REQUIRED_CHECKS (comma-separated); see required_checks().
REQUIRED_CHECKS: frozenset[str] = frozenset({
    "lint",
    "path-guard",
    "security",
    "store-import-guard",
    "surface-drift",
    "audit-verify",
    "pytest-matrix (3.11, true)",
    "pytest-matrix (3.12, false)",
})

# Only these repos can satisfy VERIFIED — arbitrary forks cannot (their
# ORCH_COMPLETION_ALLOWED_REPOS). Override with WILLOW_COMPLETION_ALLOWED_REPOS
# (comma-separated); see allowed_repos().
ALLOWED_REPOS: frozenset[str] = frozenset({"rudi193-cmd/willow-2.0"})

# A green check only counts if it came from a trusted app — stops a malicious
# self-hosted runner from rubber-stamping its own success.
TRUSTED_CHECK_APPS: frozenset[str] = frozenset({"github-actions"})

# Enforcement flag — default-off. When unset/false the gate is advisory: the
# dispatch close still records a verdict but never blocks. See gate_enabled().
GATE_ENV = "WILLOW_COMPLETION_REQUIRE_EVIDENCE"

GhCaller = Callable[[str], Any]

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _env_frozenset(name: str, default: frozenset[str]) -> frozenset[str]:
    """Return a comma-separated env override as a frozenset, else `default`.
    Empty/whitespace-only values fall back to the default (never an empty set)."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    parts = frozenset(p.strip() for p in raw.split(",") if p.strip())
    return parts or default


def required_checks() -> frozenset[str]:
    """Required-checks gate, env-overridable via WILLOW_COMPLETION_REQUIRED_CHECKS."""
    return _env_frozenset("WILLOW_COMPLETION_REQUIRED_CHECKS", REQUIRED_CHECKS)


def allowed_repos() -> frozenset[str]:
    """Repo allowlist, env-overridable via WILLOW_COMPLETION_ALLOWED_REPOS."""
    return _env_frozenset("WILLOW_COMPLETION_ALLOWED_REPOS", ALLOWED_REPOS)


def gate_enabled() -> bool:
    """True when the completion gate is set to enforce (default-off)."""
    return os.environ.get(GATE_ENV, "").strip().lower() in _TRUTHY


def _gh_via_kart(path: str) -> Any:
    """Default `gh api <path>` caller. Runs on host/Kart-with-net at wiring time;
    returns parsed JSON or None on any failure. Never raises."""
    try:
        r = subprocess.run(
            ["gh", "api", path], capture_output=True, text=True, timeout=20,
        )
        if r.returncode != 0:
            return None
        return json.loads(r.stdout)
    except Exception:  # pragma: no cover - defensive; tests inject gh
        return None


def _check_runs(payload: Any) -> list[dict[str, Any]]:
    """Normalize a check-runs response — gh returns {check_runs: [...]}, tests
    pass the list directly."""
    if isinstance(payload, dict):
        return payload.get("check_runs", []) or []
    return payload or []


def verify_completion_evidence(
    evidence: dict[str, Any] | None,
    *,
    gh: GhCaller = _gh_via_kart,
) -> dict[str, Any]:
    """Validate a completion claim against GitHub.

    Returns {"status": "VERIFIED"|"UNVERIFIED", "reasons": [...], "checked": {...}}.
    VERIFIED requires: a commit_sha, an allowlisted repo, the commit existing on
    GitHub, and every required check (required_checks()) present as success from a
    TRUSTED app. Any shortfall yields UNVERIFIED with the specific reasons — never
    raises.
    """
    evidence = evidence or {}
    reasons: list[str] = []
    sha = str(evidence.get("commit_sha", "")).strip()
    repo = str(evidence.get("repo", "")).strip()
    repos = allowed_repos()

    if not sha:
        reasons.append("no commit_sha")
    if repo not in repos:
        reasons.append(f"repo {repo!r} not allowlisted")

    if not reasons:
        if not gh(f"repos/{repo}/commits/{sha}"):
            reasons.append("commit not found on GitHub")

    if not reasons:
        runs = _check_runs(gh(f"repos/{repo}/commits/{sha}/check-runs?per_page=100"))
        passed = {
            c.get("name")
            for c in runs
            if c.get("conclusion") == "success"
            and (c.get("app") or {}).get("slug") in TRUSTED_CHECK_APPS
        }
        missing = required_checks() - passed
        if missing:
            reasons.append(f"checks not green/trusted: {sorted(missing)}")

    return {
        "status": "UNVERIFIED" if reasons else "VERIFIED",
        "reasons": reasons,
        "checked": {"sha": sha, "repo": repo},
    }


def self_close_rejection(app_id: str, task: dict[str, Any]) -> dict[str, Any] | None:
    """Block a supervised worker from closing its own dispatch task.

    Willow's analog of their `peer_self_completion_rejection`, keyed on the
    explicit `from_agent` (supervisor) / `to_agent` (worker) columns rather than a
    parsed name suffix. Returns a 409-style redirect payload when the caller is the
    worker trying to self-close, or None when the close is allowed (no supervisor,
    self-managed task, or the supervisor/another party closing).
    """
    worker = str(task.get("to_agent", "")).strip()
    supervisor = str(task.get("from_agent", "")).strip()
    if not supervisor or supervisor == worker:
        return None  # self-managed — no separation of duties to enforce
    if app_id != worker:
        return None  # supervisor (or operator) is closing — allowed
    return {
        "status": 409,
        "error": "supervised worker cannot self-close its own task",
        "do_instead": (
            "agent_dispatch_result(dispatch_id, result, role='report', evidence={...}); "
            f"{supervisor} closes after verify_completion_evidence passes"
        ),
    }
