"""Tests for core.code_version — server staleness detection.

Drives the comparison logic with a fake _git so it does not depend on the
live repo's HEAD. Runs in CI without network or a moving checkout.
"""

from __future__ import annotations

import core.code_version as cv


def _fake_git(mapping):
    """Return a _git stand-in driven by a {args_tuple: result} mapping."""
    def _g(args):
        return mapping.get(tuple(args))
    return _g


def setup_function():
    cv.boot_sha.cache_clear()


def teardown_function():
    cv.boot_sha.cache_clear()


def test_in_sync_is_not_stale(monkeypatch):
    sha = "a" * 40
    monkeypatch.setattr(cv, "_git", _fake_git({("rev-parse", "HEAD"): sha}))
    info = cv.staleness()
    assert info["stale"] is False
    assert info["commits_behind"] == 0
    assert info["booted_sha"] == sha[:8]
    assert info["head_sha"] == sha[:8]


def test_behind_head_is_stale(monkeypatch):
    booted, head = "a" * 40, "b" * 40
    # boot_sha() is primed first (cached), then HEAD advances to `head`.
    seq = {("rev-parse", "HEAD"): booted}
    monkeypatch.setattr(cv, "_git", _fake_git(seq))
    cv.boot_sha()  # prime cache at `booted`
    seq[("rev-parse", "HEAD")] = head
    seq[("rev-list", "--count", f"{booted}..{head}")] = "3"
    info = cv.staleness()
    assert info["stale"] is True
    assert info["commits_behind"] == 3
    assert "fleet_restart" in info["note"]


def test_git_unavailable_reports_unknown(monkeypatch):
    monkeypatch.setattr(cv, "_git", lambda args: None)
    info = cv.staleness()
    assert info["stale"] is False
    assert info["booted_sha"] is None
    assert "git unavailable" in info["note"]


def test_diverged_with_zero_count_still_stale(monkeypatch):
    booted, head = "a" * 40, "b" * 40
    seq = {("rev-parse", "HEAD"): booted}
    monkeypatch.setattr(cv, "_git", _fake_git(seq))
    cv.boot_sha()
    seq[("rev-parse", "HEAD")] = head
    seq[("rev-list", "--count", f"{booted}..{head}")] = "0"  # head not ahead
    info = cv.staleness()
    assert info["stale"] is True
    assert info["commits_behind"] == 0
    assert "resync" in info["note"]


def test_real_repo_boot_sha_shape():
    # In CI this is a real git checkout; boot_sha is a 40-char hex or None.
    sha = cv.boot_sha()
    assert sha is None or (len(sha) == 40 and all(c in "0123456789abcdef" for c in sha))
