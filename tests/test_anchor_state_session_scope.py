"""tests/test_anchor_state_session_scope.py — per-session prompt_count scoping.

Regression guard for flag-handoff-prompt-count-cross-session: concurrent
sessions under one agent namespace shared a single anchor_state_{agent}.json, so
a fresh session inherited another session's count and tripped HANDOFF_NOW early.
Counters are now keyed per session_id.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import willow.fylgja.anchor_state as anchor_state  # noqa: E402


@pytest.fixture
def iso(tmp_path, monkeypatch):
    """Isolate file IO to tmp and neutralise the SOIL mirror.

    Patch core.soil.get/put directly — `from core import soil` resolves through
    the real module attribute, so a sys.modules swap would not intercept it
    (and the real SOIL store leaks state across tests).
    """
    monkeypatch.setattr(anchor_state, "willow_home", lambda: tmp_path)
    monkeypatch.setattr("core.soil.get", lambda *a, **k: None)
    monkeypatch.setattr("core.soil.put", lambda *a, **k: None)
    return anchor_state


def test_sessions_have_independent_counts(iso):
    for _ in range(3):
        iso.bump_prompt_count("willow", "sess-A")
    iso.bump_prompt_count("willow", "sess-B")
    assert iso.prompt_count("willow", "sess-A") == 3
    assert iso.prompt_count("willow", "sess-B") == 1


def test_reset_is_session_scoped(iso):
    iso.bump_prompt_count("willow", "sess-A")
    iso.bump_prompt_count("willow", "sess-A")
    iso.bump_prompt_count("willow", "sess-B")
    iso.bump_prompt_count("willow", "sess-B")
    iso.reset_prompt_count("willow", "sess-A")
    assert iso.prompt_count("willow", "sess-A") == 0
    assert iso.prompt_count("willow", "sess-B") == 2


def test_fresh_session_does_not_inherit_other_count(iso):
    """The exact bug: a busy session must not bleed into a brand-new one."""
    for _ in range(26):  # past HANDOFF_THRESHOLD
        iso.bump_prompt_count("willow", "busy")
    assert iso.context_status(agent="willow", session_id="busy") == "HANDOFF_NOW"
    # A new session starts clean.
    assert iso.prompt_count("willow", "brand-new") == 0
    assert iso.context_status(agent="willow", session_id="brand-new") == "STATUS_OK"


def test_no_session_id_reflects_newest_session_file(iso):
    """check_context.sh has no session_id — it should see the active session."""
    for _ in range(5):
        iso.bump_prompt_count("willow", "old")
    iso.bump_prompt_count("willow", "new")  # written last -> newest mtime
    assert iso.prompt_count("willow") == 1


def test_unknown_session_falls_back_to_legacy_bucket(iso):
    """Falsy / 'unknown' session_id uses the legacy per-agent file (back-compat)."""
    assert iso.state_file("willow", "unknown") == iso.state_file("willow", None)
    iso.bump_prompt_count("willow", "unknown")
    # No scoped files exist, so a session-less read hits the legacy file.
    assert iso.prompt_count("willow") == 1


def test_prune_removes_stale_session_files(iso, tmp_path):
    import os
    import time

    iso.bump_prompt_count("willow", "stale")
    iso.bump_prompt_count("willow", "recent")
    stale = iso.state_file("willow", "stale")
    old = time.time() - 72 * 3600
    os.utime(stale, (old, old))

    removed = iso.prune_session_states("willow", max_age_hours=48)
    assert removed == 1
    assert not stale.exists()
    assert iso.state_file("willow", "recent").exists()
