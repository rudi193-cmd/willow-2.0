"""Tests for evidence-gated completion (core/completion_verify).

Pure/offline: `verify_completion_evidence` takes an injectable `gh` caller, so
every path is exercised with canned GitHub responses and no network. Also covers
the `self_close_rejection` separation-of-duties guard.
"""

from __future__ import annotations

from typing import Any

from core import completion_verify as cv


def _gh_ok(sha: str = "abc123"):
    """Fake gh: commit exists, all required checks green from a trusted app."""
    runs = [{"name": n, "conclusion": "success", "app": {"slug": "github-actions"}}
            for n in cv.REQUIRED_CHECKS]

    def gh(path: str) -> Any:
        if path.endswith(f"/commits/{sha}"):
            return {"sha": sha}
        if "check-runs" in path:
            return runs
        return None
    return gh


def _ev(**kw: Any) -> dict[str, Any]:
    base = {"repo": "rudi193-cmd/willow-2.0", "commit_sha": "abc123",
            "reason": "shipped", "production_observation": "merged to master"}
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# verify_completion_evidence
# --------------------------------------------------------------------------- #


def test_verified_when_commit_and_all_checks_green():
    v = cv.verify_completion_evidence(_ev(), gh=_gh_ok())
    assert v["status"] == "VERIFIED"
    assert v["reasons"] == []
    assert v["checked"] == {"sha": "abc123", "repo": "rudi193-cmd/willow-2.0"}


def test_unverified_missing_commit_sha():
    v = cv.verify_completion_evidence(_ev(commit_sha=""), gh=_gh_ok())
    assert v["status"] == "UNVERIFIED"
    assert any("no commit_sha" in r for r in v["reasons"])


def test_unverified_repo_not_allowlisted():
    v = cv.verify_completion_evidence(_ev(repo="randomuser/willow-2.0"), gh=_gh_ok())
    assert v["status"] == "UNVERIFIED"
    assert any("not allowlisted" in r for r in v["reasons"])


def test_unverified_commit_not_found():
    v = cv.verify_completion_evidence(_ev(), gh=lambda p: None)
    assert v["status"] == "UNVERIFIED"
    assert any("not found" in r for r in v["reasons"])


def test_unverified_when_a_required_check_is_red():
    sha = "abc123"
    runs = [{"name": n, "conclusion": ("failure" if n == "security" else "success"),
             "app": {"slug": "github-actions"}} for n in cv.REQUIRED_CHECKS]
    gh = lambda p: ({"sha": sha} if p.endswith(sha) else runs if "check-runs" in p else None)  # noqa: E731
    v = cv.verify_completion_evidence(_ev(), gh=gh)
    assert v["status"] == "UNVERIFIED"
    assert any("security" in r for r in v["reasons"])


def test_unverified_when_check_from_untrusted_app():
    sha = "abc123"
    runs = [{"name": n, "conclusion": "success", "app": {"slug": "evil-bot"}}
            for n in cv.REQUIRED_CHECKS]
    gh = lambda p: ({"sha": sha} if p.endswith(sha) else runs if "check-runs" in p else None)  # noqa: E731
    v = cv.verify_completion_evidence(_ev(), gh=gh)
    assert v["status"] == "UNVERIFIED"  # success from an untrusted app does not count


def test_check_runs_dict_shape_is_normalized():
    sha = "abc123"
    runs = [{"name": n, "conclusion": "success", "app": {"slug": "github-actions"}}
            for n in cv.REQUIRED_CHECKS]
    # gh returns the real {check_runs: [...]} envelope, not a bare list
    gh = lambda p: ({"sha": sha} if p.endswith(sha)  # noqa: E731
                    else {"check_runs": runs} if "check-runs" in p else None)
    v = cv.verify_completion_evidence(_ev(), gh=gh)
    assert v["status"] == "VERIFIED"


def test_empty_evidence_is_unverified_not_crash():
    v = cv.verify_completion_evidence({}, gh=_gh_ok())
    assert v["status"] == "UNVERIFIED"


def test_none_evidence_is_unverified_not_crash():
    v = cv.verify_completion_evidence(None, gh=_gh_ok())
    assert v["status"] == "UNVERIFIED"


# --------------------------------------------------------------------------- #
# self_close_rejection
# --------------------------------------------------------------------------- #


def test_worker_cannot_self_close():
    task = {"to_agent": "loki", "from_agent": "willow"}
    out = cv.self_close_rejection("loki", task)
    assert out is not None
    assert out["status"] == 409


def test_supervisor_may_close():
    task = {"to_agent": "loki", "from_agent": "willow"}
    assert cv.self_close_rejection("willow", task) is None


def test_self_managed_task_allows_close():
    task = {"to_agent": "willow", "from_agent": "willow"}
    assert cv.self_close_rejection("willow", task) is None


def test_no_supervisor_allows_close():
    task = {"to_agent": "loki", "from_agent": ""}
    assert cv.self_close_rejection("loki", task) is None


# --------------------------------------------------------------------------- #
# is_supervised (slice 3) — scopes the evidence requirement
# --------------------------------------------------------------------------- #


def test_supervised_when_distinct_supervisor():
    assert cv.is_supervised({"to_agent": "loki", "from_agent": "willow"}) is True


def test_not_supervised_when_self_managed():
    assert cv.is_supervised({"to_agent": "willow", "from_agent": "willow"}) is False


def test_not_supervised_when_no_supervisor():
    assert cv.is_supervised({"to_agent": "loki", "from_agent": ""}) is False


def test_not_supervised_handles_whitespace_and_missing():
    assert cv.is_supervised({"to_agent": "loki", "from_agent": "  "}) is False
    assert cv.is_supervised({}) is False


# --------------------------------------------------------------------------- #
# env-overridable config (slice 2)
# --------------------------------------------------------------------------- #


def test_required_checks_default_is_the_frozenset(monkeypatch):
    monkeypatch.delenv("WILLOW_COMPLETION_REQUIRED_CHECKS", raising=False)
    assert cv.required_checks() == cv.REQUIRED_CHECKS


def test_required_checks_env_override(monkeypatch):
    monkeypatch.setenv("WILLOW_COMPLETION_REQUIRED_CHECKS", "lint, security ,build")
    assert cv.required_checks() == frozenset({"lint", "security", "build"})


def test_required_checks_blank_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("WILLOW_COMPLETION_REQUIRED_CHECKS", "   ")
    assert cv.required_checks() == cv.REQUIRED_CHECKS


def test_allowed_repos_default(monkeypatch):
    monkeypatch.delenv("WILLOW_COMPLETION_ALLOWED_REPOS", raising=False)
    assert cv.allowed_repos() == cv.ALLOWED_REPOS


def test_allowed_repos_env_override(monkeypatch):
    monkeypatch.setenv("WILLOW_COMPLETION_ALLOWED_REPOS", "me/fork,other/repo")
    assert cv.allowed_repos() == frozenset({"me/fork", "other/repo"})


def test_gate_disabled_by_default(monkeypatch):
    monkeypatch.delenv("WILLOW_COMPLETION_REQUIRE_EVIDENCE", raising=False)
    assert cv.gate_enabled() is False


def test_gate_enabled_truthy_values(monkeypatch):
    for v in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("WILLOW_COMPLETION_REQUIRE_EVIDENCE", v)
        assert cv.gate_enabled() is True


def test_gate_disabled_falsy_values(monkeypatch):
    for v in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("WILLOW_COMPLETION_REQUIRE_EVIDENCE", v)
        assert cv.gate_enabled() is False


def test_verify_honors_env_repo_allowlist(monkeypatch):
    # A repo NOT in the hardcoded default becomes valid once allowlisted via env.
    monkeypatch.setenv("WILLOW_COMPLETION_ALLOWED_REPOS", "me/fork")
    ev = {"repo": "me/fork", "commit_sha": "abc123"}
    v = cv.verify_completion_evidence(ev, gh=_gh_ok())
    assert v["status"] == "VERIFIED"


def test_verify_honors_env_required_checks(monkeypatch):
    # Narrow the required set to one check the fake gh reports green.
    monkeypatch.setenv("WILLOW_COMPLETION_REQUIRED_CHECKS", "lint")
    sha = "abc123"
    runs = [{"name": "lint", "conclusion": "success", "app": {"slug": "github-actions"}}]
    gh = lambda p: ({"sha": sha} if p.endswith(sha) else runs if "check-runs" in p else None)  # noqa: E731
    v = cv.verify_completion_evidence(_ev(), gh=gh)
    assert v["status"] == "VERIFIED"


# --------------------------------------------------------------------------- #
# named check contexts — commit-status fallback (ccfo borrow)
# --------------------------------------------------------------------------- #


def _gh_mixed(check_run_names, status_contexts, sha: str = "abc123"):
    """Fake gh serving check-runs AND commit statuses.

    check_run_names: names served as green github-actions check-runs.
    status_contexts: list of {context, state, creator} commit-status dicts.
    """
    runs = [{"name": n, "status": "completed", "conclusion": "success",
             "app": {"slug": "github-actions"}} for n in check_run_names]

    def gh(path: str) -> Any:
        if path.endswith(f"/commits/{sha}"):
            return {"sha": sha}
        if "check-runs" in path:
            return {"check_runs": runs}
        if "statuses" in path:
            return status_contexts
        return None
    return gh


def test_verified_via_trusted_status_context_when_no_check_run(monkeypatch):
    # A required gate that exists only as a trusted commit-status context (no
    # check-run at all) still satisfies VERIFIED — the core named-check borrow.
    monkeypatch.setenv("WILLOW_COMPLETION_REQUIRED_CHECKS", "external-audit")
    statuses = [{"context": "external-audit", "state": "success",
                 "creator": {"login": "github-actions[bot]"}}]
    gh = _gh_mixed(check_run_names=[], status_contexts=statuses)
    v = cv.verify_completion_evidence(_ev(), gh=gh)
    assert v["status"] == "VERIFIED", v["reasons"]
    assert any(o["kind"] == "commit-status" and o["ok"] for o in v["checks"])


def test_unverified_when_status_creator_untrusted(monkeypatch):
    monkeypatch.setenv("WILLOW_COMPLETION_REQUIRED_CHECKS", "external-audit")
    statuses = [{"context": "external-audit", "state": "success",
                 "creator": {"login": "evil-actor"}}]
    gh = _gh_mixed(check_run_names=[], status_contexts=statuses)
    v = cv.verify_completion_evidence(_ev(), gh=gh)
    assert v["status"] == "UNVERIFIED"
    assert any("external-audit" in r for r in v["reasons"])


def test_unverified_when_status_state_not_success(monkeypatch):
    monkeypatch.setenv("WILLOW_COMPLETION_REQUIRED_CHECKS", "external-audit")
    statuses = [{"context": "external-audit", "state": "pending",
                 "creator": {"login": "github-actions[bot]"}}]
    gh = _gh_mixed(check_run_names=[], status_contexts=statuses)
    v = cv.verify_completion_evidence(_ev(), gh=gh)
    assert v["status"] == "UNVERIFIED"


def test_mixed_sources_one_check_run_one_status(monkeypatch):
    # Two required gates: one satisfied by a check-run, one by a status context.
    monkeypatch.setenv("WILLOW_COMPLETION_REQUIRED_CHECKS", "lint,external-audit")
    statuses = [{"context": "external-audit", "state": "success",
                 "creator": {"login": "github-actions[bot]"}}]
    gh = _gh_mixed(check_run_names=["lint"], status_contexts=statuses)
    v = cv.verify_completion_evidence(_ev(), gh=gh)
    assert v["status"] == "VERIFIED", v["reasons"]
    kinds = {o["name"]: o["kind"] for o in v["checks"] if o["ok"]}
    assert kinds == {"lint": "check-run", "external-audit": "commit-status"}


def test_latest_status_context_wins(monkeypatch):
    # A stale failing status must not block when a newer success exists.
    monkeypatch.setenv("WILLOW_COMPLETION_REQUIRED_CHECKS", "external-audit")
    statuses = [
        {"context": "external-audit", "state": "failure", "created_at": "2026-01-01T00:00:00Z",
         "creator": {"login": "github-actions[bot]"}},
        {"context": "external-audit", "state": "success", "created_at": "2026-06-29T00:00:00Z",
         "creator": {"login": "github-actions[bot]"}},
    ]
    gh = _gh_mixed(check_run_names=[], status_contexts=statuses)
    v = cv.verify_completion_evidence(_ev(), gh=gh)
    assert v["status"] == "VERIFIED", v["reasons"]


def test_verified_result_carries_observations():
    v = cv.verify_completion_evidence(_ev(), gh=_gh_ok())
    assert v["checks"], "expected per-check observations"
    assert all(o["ok"] for o in v["checks"])
    assert {o["name"] for o in v["checks"]} == set(cv.REQUIRED_CHECKS)


def test_statuses_endpoint_not_hit_when_all_check_runs_pass():
    # Lazy: the statuses API must not be queried if every gate passes as a check-run.
    sha = "abc123"
    runs = [{"name": n, "status": "completed", "conclusion": "success",
             "app": {"slug": "github-actions"}} for n in cv.REQUIRED_CHECKS]
    hits: list[str] = []

    def gh(path: str) -> Any:
        hits.append(path)
        if path.endswith(f"/commits/{sha}"):
            return {"sha": sha}
        if "check-runs" in path:
            return runs
        return None
    v = cv.verify_completion_evidence(_ev(), gh=gh)
    assert v["status"] == "VERIFIED"
    assert not any("statuses" in p for p in hits)


# --------------------------------------------------------------------------- #
# trusted-actor config (named-check-contexts)
# --------------------------------------------------------------------------- #


def test_trusted_status_creators_default(monkeypatch):
    monkeypatch.delenv("WILLOW_COMPLETION_TRUSTED_STATUS_CREATORS", raising=False)
    assert cv.trusted_status_creators() == cv.TRUSTED_STATUS_CREATORS


def test_trusted_status_creators_env_override(monkeypatch):
    monkeypatch.setenv("WILLOW_COMPLETION_TRUSTED_STATUS_CREATORS", "a[bot], b[bot]")
    assert cv.trusted_status_creators() == frozenset({"a[bot]", "b[bot]"})


def test_trusted_check_apps_default(monkeypatch):
    monkeypatch.delenv("WILLOW_COMPLETION_TRUSTED_CHECK_APPS", raising=False)
    assert cv.trusted_check_apps() == cv.TRUSTED_CHECK_APPS


def test_trusted_check_apps_env_override(monkeypatch):
    monkeypatch.setenv("WILLOW_COMPLETION_TRUSTED_CHECK_APPS", "my-runner")
    assert cv.trusted_check_apps() == frozenset({"my-runner"})
