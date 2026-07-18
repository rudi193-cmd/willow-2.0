"""
test_kart_fast_timeout.py — fast-lane timeout (C73F90F3, Part A).

The fast lane is interactive but was inheriting the 1800s daemon ceiling
(kart_worker._process_task_row passed context="daemon" with no lane), so a hung
fast task could hold one of the few fast slots for half an hour before the 3600s
reaper cleared it. Part A gives the fast lane its own short ceiling (300s) and
makes the reaper-alignment invariant cover it.

These are the SAFE unit tests (no subprocess, no DB, no host probe). The
behavioural kill test (child process reaped at ~300s) belongs on a disposable
box only — never here.
"""
from __future__ import annotations

import pytest

from core import kart_execute
from core.kart_execute import kart_timeout, run_shell_task
from core.kart_lanes import fast_timeout_seconds, reaper_alignment_warning


# ── kart_timeout lane matrix ─────────────────────────────────────────────────

class TestKartTimeoutMatrix:
    def test_daemon_fast_gets_short_ceiling(self, monkeypatch):
        monkeypatch.delenv("KART_FAST_TIMEOUT", raising=False)
        assert kart_timeout("daemon", lane="fast") == 300

    def test_daemon_batch_keeps_daemon_ceiling(self, monkeypatch):
        monkeypatch.delenv("KART_DAEMON_TIMEOUT", raising=False)
        assert kart_timeout("daemon", lane="batch") == 1800

    def test_daemon_no_lane_is_backcompat_daemon(self, monkeypatch):
        monkeypatch.delenv("KART_DAEMON_TIMEOUT", raising=False)
        assert kart_timeout("daemon") == 1800
        assert kart_timeout("daemon", lane=None) == 1800

    def test_poll_is_short_and_lane_independent(self, monkeypatch):
        monkeypatch.delenv("KART_POLL_TIMEOUT", raising=False)
        assert kart_timeout("poll") == 120
        assert kart_timeout("poll", lane="fast") == 120
        assert kart_timeout("poll", lane="batch") == 120

    def test_fast_ceiling_is_env_overridable(self, monkeypatch):
        monkeypatch.setenv("KART_FAST_TIMEOUT", "90")
        assert fast_timeout_seconds() == 90
        assert kart_timeout("daemon", lane="fast") == 90

    def test_empty_lane_string_normalizes_to_fast(self, monkeypatch):
        # normalize_lane treats "" as the fast default, so an empty lane column
        # still gets the fast ceiling, not the daemon one.
        monkeypatch.delenv("KART_FAST_TIMEOUT", raising=False)
        assert kart_timeout("daemon", lane="") == 300


# ── reaper alignment covers the fast lane ────────────────────────────────────

class TestReaperAlignment:
    def test_defaults_are_aligned(self, monkeypatch):
        for k in ("KART_STALE_SECONDS", "KART_DAEMON_TIMEOUT", "KART_FAST_TIMEOUT"):
            monkeypatch.delenv(k, raising=False)
        # stale 3600 > max(1800, 300) + 300 buffer → no warning
        assert reaper_alignment_warning() is None

    def test_flags_fast_timeout_at_or_above_reaper(self, monkeypatch):
        # a misconfigured fast timeout >= reaper must be flagged — a fast task
        # would then be reaped rather than dying by its own ceiling.
        monkeypatch.setenv("KART_STALE_SECONDS", "3600")
        monkeypatch.setenv("KART_DAEMON_TIMEOUT", "1800")
        monkeypatch.setenv("KART_FAST_TIMEOUT", "4000")
        warn = reaper_alignment_warning()
        assert warn is not None
        assert "KART_FAST_TIMEOUT" in warn

    def test_flags_daemon_timeout_too_close_to_reaper(self, monkeypatch):
        monkeypatch.setenv("KART_STALE_SECONDS", "1900")  # < 1800 + 300 buffer
        monkeypatch.setenv("KART_DAEMON_TIMEOUT", "1800")
        monkeypatch.delenv("KART_FAST_TIMEOUT", raising=False)
        warn = reaper_alignment_warning()
        assert warn is not None
        assert "KART_DAEMON_TIMEOUT" in warn


# ── the ceiling actually reaches the executor ────────────────────────────────

class TestLaneThreadsToExecutor:
    """run_shell_task must hand the lane-correct ceiling to the shell runner."""

    def _capture(self, monkeypatch):
        seen = {}

        def fake_run_one_shell(cmd, *, timeout, allow_net, allow_localhost):
            seen["timeout"] = timeout
            return "completed", {"returncode": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(kart_execute, "_run_one_shell", fake_run_one_shell)
        return seen

    def test_daemon_fast_task_runs_at_300(self, monkeypatch):
        monkeypatch.delenv("KART_FAST_TIMEOUT", raising=False)
        seen = self._capture(monkeypatch)
        run_shell_task("echo hi", context="daemon", lane="fast", net_authorized=True)
        assert seen["timeout"] == 300

    def test_daemon_batch_task_runs_at_1800(self, monkeypatch):
        monkeypatch.delenv("KART_DAEMON_TIMEOUT", raising=False)
        seen = self._capture(monkeypatch)
        run_shell_task("echo hi", context="daemon", lane="batch", net_authorized=True)
        assert seen["timeout"] == 1800

    def test_explicit_timeout_still_wins(self, monkeypatch):
        seen = self._capture(monkeypatch)
        run_shell_task("echo hi", timeout=42, context="daemon", lane="fast")
        assert seen["timeout"] == 42


class TestRowLaneDerivation:
    """_dispatch_task_row must read the lane off the row and pass it down, so the
    worker's fast rows get the fast ceiling without threading lane by hand."""

    def test_dispatch_passes_row_lane_to_run_shell_task(self, monkeypatch):
        seen = {}

        def fake_run_shell_task(cmd, *, timeout, context, lane, net_authorized, net_denied_reason):
            seen["lane"] = lane
            seen["context"] = context
            return "completed", {"returncode": 0}

        monkeypatch.setattr(kart_execute, "run_shell_task", fake_run_shell_task)
        # keep the egress resolver hermetic (no key/DB read)
        monkeypatch.setattr(
            "core.egress_authority.net_authorized", lambda who: (False, ""), raising=False
        )
        row = {"id": "t1", "task": "echo hi", "lane": "fast", "submitted_by": "kart"}
        kart_execute._dispatch_task_row(row, pg=None, timeout=None, context="daemon")
        assert seen["lane"] == "fast"
        assert seen["context"] == "daemon"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
