"""
Read-time claim verification for handoff v3.

Each claim carries {kind, verify: {type, subject, expect}}. The boot digest
calls verify_claims() when the handoff is CONSUMED — verdicts are stamped into
digest output with checked_at and are never written back into the handoff.

Verdict statuses:
  verified     — the check ran and matched expectation
  failed       — the check ran and did NOT match (stale claim; do not act on it)
  unverifiable — kind=prose, or the checker's data source is unreachable
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

_GIT_TIMEOUT = 6
_GH_TIMEOUT = 8


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _verdict(status: str, detail: str = "") -> dict:
    return {"status": status, "detail": detail[:200], "checked_at": _now()}


def _run(cmd: list[str], cwd: Path | None, timeout: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
        return proc.returncode, (proc.stdout or proc.stderr).strip()
    except Exception as exc:
        return -1, str(exc)


def _check_branch_pushed(subject: str, repo_root: Path) -> dict:
    code, out = _run(
        ["git", "rev-parse", "--verify", "--quiet", f"origin/{subject}"],
        repo_root, _GIT_TIMEOUT,
    )
    if code == 0 and out:
        return _verdict("verified", f"origin/{subject} at {out[:12]}")
    if code == -1:
        return _verdict("unverifiable", out)
    return _verdict("failed", f"origin/{subject} not found locally")


def _check_pr_state(subject: str, expect: object, repo_root: Path) -> dict:
    # subject: "123" or "owner/repo#123"
    repo = ""
    number = subject
    if "#" in subject:
        repo, _, number = subject.partition("#")
    cmd = ["gh", "pr", "view", number, "--json", "state", "--jq", ".state"]
    if repo:
        cmd[2:2] = ["--repo", repo]
    code, out = _run(cmd, repo_root, _GH_TIMEOUT)
    if code != 0:
        return _verdict("unverifiable", f"gh failed: {out[:120]}")
    state = out.strip().lower()
    expected = str(expect or "open").strip().lower()
    if state == expected:
        return _verdict("verified", f"PR {subject} is {state}")
    return _verdict("failed", f"PR {subject} is {state}, expected {expected}")


def _check_file_exists(subject: str, expect: object, repo_root: Path) -> dict:
    path = Path(subject)
    if not path.is_absolute():
        path = repo_root / subject
    exists = path.exists()
    expected = True if expect is None else bool(expect)
    if exists == expected:
        return _verdict("verified", f"{subject} exists={exists}")
    return _verdict("failed", f"{subject} exists={exists}, expected {expected}")


def _check_flag_open(subject: str, expect: object, agent: str) -> dict:
    try:
        from core.store_port import get_store_port

        store = get_store_port()
        record = store.get(f"{agent}/flags", subject) or {}
        is_open = record.get("flag_state") in ("open", "running", "awaiting_authorization")
        expected = True if expect is None else bool(expect)
        if bool(is_open) == expected:
            return _verdict("verified", f"flag {subject} open={is_open}")
        return _verdict("failed", f"flag {subject} open={is_open}, expected {expected}")
    except Exception as exc:
        return _verdict("unverifiable", f"store unreachable: {exc}")


def _check_sha_current(subject: str, repo_root: Path) -> dict:
    code, _ = _run(
        ["git", "merge-base", "--is-ancestor", subject, "HEAD"],
        repo_root, _GIT_TIMEOUT,
    )
    if code == 0:
        return _verdict("verified", f"{subject[:12]} is an ancestor of HEAD")
    if code == 1:
        return _verdict("failed", f"{subject[:12]} not reachable from HEAD")
    return _verdict("unverifiable", "git merge-base failed")


def verify_claim(claim: dict, *, repo_root: str | Path = "", agent: str = "willow") -> dict:
    """Verify one claim. Never raises; unknown kinds are unverifiable."""
    root = Path(repo_root) if repo_root else Path.cwd()
    kind = str(claim.get("kind") or "")
    verify = claim.get("verify") if isinstance(claim.get("verify"), dict) else {}
    subject = str(verify.get("subject") or "").strip()
    expect = verify.get("expect")

    if kind == "prose":
        return _verdict("unverifiable", "prose claim — declared unverifiable")
    if not subject:
        return _verdict("unverifiable", "no verify.subject")
    try:
        if kind == "branch_pushed":
            return _check_branch_pushed(subject, root)
        if kind == "pr_state":
            return _check_pr_state(subject, expect, root)
        if kind == "file_exists":
            return _check_file_exists(subject, expect, root)
        if kind == "flag_open":
            return _check_flag_open(subject, expect, agent)
        if kind == "sha_current":
            return _check_sha_current(subject, root)
    except Exception as exc:
        return _verdict("unverifiable", f"checker error: {exc}")
    return _verdict("unverifiable", f"unknown claim kind {kind!r}")


def verify_claims(
    claims: list[dict],
    *,
    repo_root: str | Path = "",
    agent: str = "willow",
    max_claims: int = 20,
) -> list[dict]:
    """Verify claims in order; returns [{**claim, verdict}]. Caps work at max_claims."""
    out: list[dict] = []
    for i, claim in enumerate(claims or []):
        if not isinstance(claim, dict):
            continue
        if i >= max_claims:
            out.append({**claim, "verdict": _verdict("unverifiable", "claim budget exceeded")})
            continue
        out.append({**claim, "verdict": verify_claim(claim, repo_root=repo_root, agent=agent)})
    return out
