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

Named-check-contexts (ccfo borrow): a required gate is satisfied by EITHER a
trusted check-run (Checks API) OR a trusted commit-status context (legacy
Statuses API). The two GitHub surfaces are distinct — external auditors and some
third-party CI post *status contexts*, not check-runs — so verifying only
check-runs left a "required gate is green but invisible" gap. Each source has its
own trusted-actor allowlist (apps for check-runs, creator logins for statuses) so
an untrusted token cannot forge a passing context. Per-check observations are
returned for an auditable trail.

Config seam (slice 2): the required-checks set, the allowlisted repos, the
trusted actors, and the enforcement flag are all env-overridable so the gate can
ship default-off and be tightened per-deployment without a code change. Env is
read at call time, so the defaults below remain the pinned public surface the
tests iterate over.
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
    "ide-parity",
    "audit-verify",
    "pytest-matrix (3.11, true)",
    "pytest-matrix (3.12, false)",
})

# Only these repos can satisfy VERIFIED — arbitrary forks cannot (their
# ORCH_COMPLETION_ALLOWED_REPOS). Override with WILLOW_COMPLETION_ALLOWED_REPOS
# (comma-separated); see allowed_repos().
ALLOWED_REPOS: frozenset[str] = frozenset({"rudi193-cmd/willow-2.0"})

# A green check-run only counts if it came from a trusted app — stops a malicious
# self-hosted runner from rubber-stamping its own success. Override with
# WILLOW_COMPLETION_TRUSTED_CHECK_APPS; see trusted_check_apps().
TRUSTED_CHECK_APPS: frozenset[str] = frozenset({"github-actions"})

# A green commit-status context only counts if its creator is trusted — the
# Statuses-API analog of TRUSTED_CHECK_APPS, keyed on the creator login (GitHub
# Actions posts statuses as "github-actions[bot]"). Override with
# WILLOW_COMPLETION_TRUSTED_STATUS_CREATORS; see trusted_status_creators().
TRUSTED_STATUS_CREATORS: frozenset[str] = frozenset({"github-actions[bot]"})

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


def trusted_check_apps() -> frozenset[str]:
    """Trusted check-run apps, env-overridable via WILLOW_COMPLETION_TRUSTED_CHECK_APPS."""
    return _env_frozenset("WILLOW_COMPLETION_TRUSTED_CHECK_APPS", TRUSTED_CHECK_APPS)


def trusted_status_creators() -> frozenset[str]:
    """Trusted commit-status creators, env-overridable via
    WILLOW_COMPLETION_TRUSTED_STATUS_CREATORS."""
    return _env_frozenset(
        "WILLOW_COMPLETION_TRUSTED_STATUS_CREATORS", TRUSTED_STATUS_CREATORS
    )


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


def _statuses(payload: Any) -> list[dict[str, Any]]:
    """Normalize a commit-statuses response — gh returns a bare [...] list, but
    tolerate a {statuses: [...]} envelope too."""
    if isinstance(payload, dict):
        return payload.get("statuses", []) or []
    return payload or []


def _app_slug(run: dict[str, Any]) -> str:
    app = run.get("app")
    return str((app or {}).get("slug") or "").strip() if isinstance(app, dict) else ""


def _status_creator(status: dict[str, Any]) -> str:
    creator = status.get("creator")
    return str((creator or {}).get("login") or "").strip() if isinstance(creator, dict) else ""


def _latest_named(items: list[dict[str, Any]], field: str, name: str) -> dict[str, Any] | None:
    """Newest item whose `field` equals `name` (a check may be re-run). Sorts by
    the available timestamps; items without timestamps sort stably to the end."""
    matches = [it for it in items if it.get(field) == name]
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda it: it.get("completed_at") or it.get("started_at")
        or it.get("created_at") or "",
        reverse=True,
    )[0]


def _eval_check_run(runs: list[dict[str, Any]], name: str) -> tuple[bool, dict[str, Any]]:
    """A required gate passes as a check-run when the latest run of that name is a
    success from a trusted app. GitHub only sets `conclusion` once `status` is
    completed, so success implies completed."""
    run = _latest_named(runs, "name", name)
    if not run:
        return False, {"name": name, "kind": "check-run", "ok": False,
                       "detail": "missing check-run"}
    conclusion = run.get("conclusion")
    slug = _app_slug(run)
    trusted = slug.lower() in {a.lower() for a in trusted_check_apps()}
    ok = conclusion == "success" and trusted
    return ok, {
        "name": name, "kind": "check-run", "ok": ok,
        "detail": f"conclusion={conclusion} app={slug or 'missing'} trusted_app={trusted}",
        "url": run.get("html_url") or run.get("details_url"),
    }


def _eval_status(statuses: list[dict[str, Any]], name: str) -> tuple[bool, dict[str, Any]]:
    """A required gate passes as a commit-status context when the latest status of
    that context is `success` from a trusted creator login."""
    status = _latest_named(statuses, "context", name)
    if not status:
        return False, {"name": name, "kind": "commit-status", "ok": False,
                       "detail": "missing commit status"}
    state = status.get("state")
    creator = _status_creator(status)
    trusted = creator.lower() in {c.lower() for c in trusted_status_creators()}
    ok = state == "success" and trusted
    return ok, {
        "name": name, "kind": "commit-status", "ok": ok,
        "detail": f"state={state} creator={creator or 'missing'} trusted_creator={trusted}",
        "url": status.get("target_url"),
    }


def verify_completion_evidence(
    evidence: dict[str, Any] | None,
    *,
    gh: GhCaller = _gh_via_kart,
) -> dict[str, Any]:
    """Validate a completion claim against GitHub.

    Returns {"status": "VERIFIED"|"UNVERIFIED", "reasons": [...], "checked": {...},
    "checks": [observation, ...]}. VERIFIED requires: a commit_sha, an allowlisted
    repo, the commit existing on GitHub, and every required check satisfied by
    EITHER a trusted check-run OR a trusted commit-status context for that exact
    sha. Any shortfall yields UNVERIFIED with the specific reasons — never raises.
    """
    evidence = evidence or {}
    reasons: list[str] = []
    observations: list[dict[str, Any]] = []
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
        statuses: list[dict[str, Any]] | None = None  # fetched lazily, only if needed
        failures: list[str] = []
        for check in sorted(required_checks()):
            run_ok, run_obs = _eval_check_run(runs, check)
            if run_ok:
                observations.append(run_obs)
                continue
            if statuses is None:
                statuses = _statuses(gh(f"repos/{repo}/commits/{sha}/statuses?per_page=100"))
            status_ok, status_obs = _eval_status(statuses, check)
            if status_ok:
                observations.append(status_obs)
                continue
            observations.extend([run_obs, status_obs])
            failures.append(f"{check}: {run_obs['detail']}; {status_obs['detail']}")
        if failures:
            reasons.append("required checks not green/trusted: " + "; ".join(failures))

    return {
        "status": "UNVERIFIED" if reasons else "VERIFIED",
        "reasons": reasons,
        "checked": {"sha": sha, "repo": repo},
        "checks": observations,
    }


def is_supervised(task: dict[str, Any]) -> bool:
    """True when the task has a distinct supervisor (from_agent != to_agent).

    Separation of duties — and therefore the VERIFIED-evidence requirement on
    close — applies only to supervised tasks. A self-managed task (from_agent
    blank or equal to to_agent) returns False and is never evidence-gated; that is
    the common willow self-dispatch path, which must keep its pre-gate behavior so
    enabling the gate does not break ordinary, non-code dispatch closes.
    """
    worker = str(task.get("to_agent", "")).strip()
    supervisor = str(task.get("from_agent", "")).strip()
    return bool(supervisor) and supervisor != worker


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
