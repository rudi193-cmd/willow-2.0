"""
tests/test_context_dedup.py — Unit tests for willow.context.dedup

No network, no DB, no filesystem writes for the core logic.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# Make sure we can import from the worktree root
sys.path.insert(0, str(Path(__file__).parent.parent))

from willow.context import dedup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fresh_session() -> dedup.DedupSession:
    """Return a brand-new session (no global state leakage)."""
    return dedup.DedupSession()


def _fake_mtime(_path: str) -> float:
    return 1234567890.0  # stable fake mtime


# ---------------------------------------------------------------------------
# Basic record + check
# ---------------------------------------------------------------------------

class TestBasicDedup:
    def test_first_read_is_allowed(self):
        s = fresh_session()
        with patch.object(dedup.DedupSession, "_current_mtime", return_value=1.0):
            result = s.check_file("/some/file.py", offset=0, limit=0)
        assert result["action"] == "allow"
        assert result["already_read"] is False
        assert result["previous_ranges"] == []

    def test_duplicate_full_read_warns(self):
        s = fresh_session()
        with patch.object(dedup.DedupSession, "_current_mtime", return_value=1.0):
            s.record_read("/some/file.py", offset=0, limit=0, line_count=50)
            result = s.check_file("/some/file.py", offset=0, limit=0)
        assert result["action"] == "warn"
        assert result["already_read"] is True
        assert "[DEDUP]" in result["message"]

    def test_full_read_covers_partial_request(self):
        """After a full read, any partial read of the same file should warn."""
        s = fresh_session()
        with patch.object(dedup.DedupSession, "_current_mtime", return_value=1.0):
            s.record_read("/some/file.py", offset=0, limit=0)
            result = s.check_file("/some/file.py", offset=50, limit=100)
        assert result["action"] == "warn"
        assert result["already_read"] is True

    def test_different_files_are_independent(self):
        s = fresh_session()
        with patch.object(dedup.DedupSession, "_current_mtime", return_value=1.0):
            s.record_read("/a.py", offset=0, limit=0)
            result = s.check_file("/b.py", offset=0, limit=0)
        assert result["action"] == "allow"
        assert result["already_read"] is False

    def test_partial_ranges_allow_new_range(self):
        """Two different partial reads of the same file — second should be allowed."""
        s = fresh_session()
        with patch.object(dedup.DedupSession, "_current_mtime", return_value=1.0):
            s.record_read("/file.py", offset=0, limit=50)
            result = s.check_file("/file.py", offset=100, limit=50)
        assert result["action"] == "allow"


# ---------------------------------------------------------------------------
# mtime invalidation
# ---------------------------------------------------------------------------

class TestMtimeInvalidation:
    def test_changed_mtime_clears_dedup(self):
        """If mtime changed, the old record is invalidated — re-read is allowed."""
        s = fresh_session()
        # First read — mtime 1.0
        with patch.object(dedup.DedupSession, "_current_mtime", return_value=1.0):
            s.record_read("/edited.py", offset=0, limit=0)
        # File was modified — mtime 2.0
        with patch.object(dedup.DedupSession, "_current_mtime", return_value=2.0):
            result = s.check_file("/edited.py", offset=0, limit=0)
        assert result["action"] == "allow", "Changed mtime should invalidate dedup"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_empty_stats(self):
        s = fresh_session()
        st = s.stats()
        assert st["total_reads"] == 0
        assert st["unique_files"] == 0
        assert st["estimated_tokens_saved"] == 0

    def test_tokens_saved_accumulate(self):
        s = fresh_session()
        with patch.object(dedup.DedupSession, "_current_mtime", return_value=1.0):
            s.record_read("/f.py", offset=0, limit=0, line_count=100)
            s.check_file("/f.py", offset=0, limit=0)  # triggers token save
        assert s.tokens_saved > 0

    def test_unique_file_count(self):
        s = fresh_session()
        with patch.object(dedup.DedupSession, "_current_mtime", return_value=1.0):
            s.record_read("/a.py")
            s.record_read("/b.py")
            s.record_read("/a.py")  # duplicate
        assert s.stats()["unique_files"] == 2
        assert s.stats()["total_reads"] == 3


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_state(self):
        s = fresh_session()
        with patch.object(dedup.DedupSession, "_current_mtime", return_value=1.0):
            s.record_read("/file.py")
        assert s.stats()["total_reads"] == 1
        s.reset()
        assert s.stats()["total_reads"] == 0
        assert s.tokens_saved == 0


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def setup_method(self):
        dedup.reset_session()

    def teardown_method(self):
        dedup.reset_session()

    def test_get_session_returns_same_object(self):
        s1 = dedup.get_session()
        s2 = dedup.get_session()
        assert s1 is s2

    def test_reset_session_returns_fresh(self):
        s1 = dedup.get_session()
        s2 = dedup.reset_session()
        assert s1 is not s2
        assert dedup.get_session() is s2


# ---------------------------------------------------------------------------
# check_and_record (hook entry point)
# ---------------------------------------------------------------------------

class TestCheckAndRecord:
    def setup_method(self):
        dedup.reset_session()

    def teardown_method(self):
        dedup.reset_session()

    def test_first_call_returns_none(self):
        with patch.object(dedup.DedupSession, "_current_mtime", return_value=1.0):
            result = dedup.check_and_record("/new.py", offset=0, limit=0)
        assert result is None

    def test_second_call_returns_advisory(self):
        with patch.object(dedup.DedupSession, "_current_mtime", return_value=1.0):
            dedup.check_and_record("/repeated.py", offset=0, limit=0)
            result = dedup.check_and_record("/repeated.py", offset=0, limit=0)
        assert result is not None
        assert "[DEDUP]" in result

    def test_different_files_no_advisory(self):
        with patch.object(dedup.DedupSession, "_current_mtime", return_value=1.0):
            dedup.check_and_record("/a.py")
            result = dedup.check_and_record("/b.py")
        assert result is None
