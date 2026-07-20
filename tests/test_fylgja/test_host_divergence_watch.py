"""Tests for the host-divergence watchdog.

The failure this watchdog exists to catch is silent, so its own silent-failure
modes get the most attention here: a broken arm must never read as "no
divergence found", and build_home() must actually flip the branch it claims to.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from willow.fylgja import host_divergence_watch as hdw


def test_plugin_pins_predicate_true(monkeypatch):
    from willow.fylgja import host_divergence_plugin, willow_home

    monkeypatch.setattr(willow_home, "private_config_available", lambda: False)
    monkeypatch.setenv("WILLOW_FORCE_PRIVATE_CONFIG", "1")
    host_divergence_plugin.pytest_configure(None)

    assert willow_home.private_config_available() is True


def test_plugin_pins_predicate_false(monkeypatch):
    from willow.fylgja import host_divergence_plugin, willow_home

    monkeypatch.setattr(willow_home, "private_config_available", lambda: True)
    monkeypatch.setenv("WILLOW_FORCE_PRIVATE_CONFIG", "0")
    host_divergence_plugin.pytest_configure(None)

    assert willow_home.private_config_available() is False


def test_plugin_is_inert_without_the_env_var(monkeypatch):
    """Loaded but undriven, it must not touch an ordinary pytest run."""
    from willow.fylgja import host_divergence_plugin, willow_home

    sentinel = object()
    monkeypatch.setattr(willow_home, "private_config_available", lambda: sentinel)
    monkeypatch.delenv("WILLOW_FORCE_PRIVATE_CONFIG", raising=False)
    host_divergence_plugin.pytest_configure(None)

    assert willow_home.private_config_available() is sentinel


def test_run_arm_varies_only_the_predicate(tmp_path, monkeypatch):
    """An arm that differs from its twin in more than one way cannot attribute a
    finding to any of them. HOME is the tempting lever — private_home() reads
    Path.home() — and the wrong one: it drags every other HOME-derived path with
    it."""
    monkeypatch.setenv("HOME", "/real/home")
    monkeypatch.setenv("WILLOW_HOME", "/real/fleet")
    monkeypatch.setenv("WILLOW_STORE_ROOT", "/real/store")
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen["env"] = kwargs.get("env") or {}
        seen["cmd"] = cmd
        return None

    monkeypatch.setattr(hdw.subprocess, "run", fake_run)
    hdw.run_arm("tests/", True, tmp_path / "private_config.xml")

    assert seen["env"]["WILLOW_FORCE_PRIVATE_CONFIG"] == "1"
    assert seen["env"]["HOME"] == "/real/home"
    assert seen["env"]["WILLOW_HOME"] == "/real/fleet"
    assert seen["env"]["WILLOW_STORE_ROOT"] == "/real/store"
    assert "-p" in seen["cmd"] and hdw.PLUGIN in seen["cmd"]


def test_run_arm_public_sets_predicate_to_zero(tmp_path, monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(hdw.subprocess, "run", lambda cmd, **k: seen.update(k.get("env") or {}))
    hdw.run_arm("tests/", False, tmp_path / "public_fallback.xml")

    assert seen["WILLOW_FORCE_PRIVATE_CONFIG"] == "0"


def test_compare_flags_outcome_flip():
    arms = {
        "private_config": {"t::a": "failed", "t::b": "passed"},
        "public_fallback": {"t::a": "passed", "t::b": "passed"},
    }
    findings = hdw.compare(arms)

    assert findings == [
        {"test": "t::a", "private_config": "failed", "public_fallback": "passed"}
    ]


def test_compare_flags_test_present_in_only_one_arm():
    arms = {
        "private_config": {"t::a": "passed"},
        "public_fallback": {"t::a": "passed", "t::b": "passed"},
    }
    findings = hdw.compare(arms)

    assert findings == [
        {"test": "t::b", "private_config": "absent", "public_fallback": "passed"}
    ]


def test_compare_silent_when_arms_agree():
    arms = {
        "private_config": {"t::a": "passed", "t::b": "failed"},
        "public_fallback": {"t::a": "passed", "t::b": "failed"},
    }

    assert hdw.compare(arms) == []


def test_parse_report_reads_outcomes(tmp_path):
    report = tmp_path / "j.xml"
    report.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
        <testsuites><testsuite name="pytest">
          <testcase classname="tests.test_x" name="test_ok"/>
          <testcase classname="tests.test_x" name="test_bad"><failure message="boom"/></testcase>
          <testcase classname="tests.test_x" name="test_err"><error message="kaboom"/></testcase>
          <testcase classname="tests.test_x" name="test_skip"><skipped message="nope"/></testcase>
        </testsuite></testsuites>""",
        encoding="utf-8",
    )

    assert hdw.parse_report(report) == {
        "tests.test_x::test_ok": "passed",
        "tests.test_x::test_bad": "failed",
        "tests.test_x::test_err": "error",
        "tests.test_x::test_skip": "skipped",
    }


def test_run_arm_announces_start_and_finish(tmp_path, monkeypatch, capsys):
    """A minutes-long arm with pytest output captured must still say it is alive."""
    report = tmp_path / "private_config.xml"

    def fake_run(cmd, **kwargs):
        report.write_text(
            '<testsuites><testsuite name="pytest">'
            '<testcase classname="t" name="ok"/>'
            '<testcase classname="t" name="bad"><failure message="x"/></testcase>'
            "</testsuite></testsuites>",
            encoding="utf-8",
        )
        return None

    monkeypatch.setattr(hdw.subprocess, "run", fake_run)
    hdw.run_arm("tests/", True, report)
    out = capsys.readouterr().out

    assert "arm private_config starting" in out
    assert "arm private_config done" in out
    assert "2 test(s), 1 failed/error" in out


def test_run_arm_reports_error_when_pytest_writes_no_report(tmp_path, monkeypatch):
    monkeypatch.setattr(hdw.subprocess, "run", lambda *a, **k: None)
    outcomes, error = hdw.run_arm("tests/", True, tmp_path / "missing.xml")

    assert outcomes == {}
    assert "no junit report" in error


def test_main_exits_2_and_marks_heartbeat_failed_when_an_arm_breaks(monkeypatch, capsys):
    """A broken arm must not be reported as a clean bill of health."""
    monkeypatch.setattr(hdw, "run_arm", lambda *a, **k: ({}, "pytest timed out after 1800s"))
    beats: list[dict] = []
    monkeypatch.setattr(
        hdw, "write_heartbeat",
        lambda tick_ok, counts, error="": beats.append({"tick_ok": tick_ok, "error": error}),
    )
    monkeypatch.setattr(hdw, "open_flag", lambda *a, **k: pytest.fail("must not flag on a broken arm"))
    monkeypatch.setattr("sys.argv", ["host_divergence_watch.py", "--dry-run", "--no-warmup"])

    assert hdw.main() == 2
    assert beats and beats[0]["tick_ok"] is False
    assert "timed out" in beats[0]["error"]
    assert "FAILED to run" in capsys.readouterr().err


def test_main_exits_1_and_flags_on_divergence(monkeypatch):
    def fake_run_arm(path, private, report):
        return ({"t::a": "failed" if private else "passed"}, "")

    monkeypatch.setattr(hdw, "run_arm", fake_run_arm)
    monkeypatch.setattr(hdw, "write_heartbeat", lambda *a, **k: None)
    flagged: list = []
    monkeypatch.setattr(hdw, "open_flag", lambda findings, counts: flagged.append(findings))
    monkeypatch.setattr("sys.argv", ["host_divergence_watch.py", "--no-warmup"])

    assert hdw.main() == 1
    assert flagged and flagged[0][0]["test"] == "t::a"


def test_main_dry_run_does_not_flag(monkeypatch):
    def fake_run_arm(path, private, report):
        return ({"t::a": "failed" if private else "passed"}, "")

    monkeypatch.setattr(hdw, "run_arm", fake_run_arm)
    monkeypatch.setattr(hdw, "write_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(hdw, "open_flag", lambda *a, **k: pytest.fail("dry-run must not flag"))
    monkeypatch.setattr("sys.argv", ["host_divergence_watch.py", "--dry-run", "--no-warmup"])

    assert hdw.main() == 1


def test_main_exits_0_and_heartbeats_when_arms_agree(monkeypatch):
    monkeypatch.setattr(hdw, "run_arm", lambda *a, **k: ({"t::a": "passed"}, ""))
    beats: list[dict] = []
    monkeypatch.setattr(
        hdw, "write_heartbeat",
        lambda tick_ok, counts, error="": beats.append({"tick_ok": tick_ok, "counts": counts}),
    )
    monkeypatch.setattr("sys.argv", ["host_divergence_watch.py", "--no-warmup"])

    assert hdw.main() == 0
    assert beats and beats[0]["tick_ok"] is True
    assert beats[0]["counts"]["diverged"] == 0


def test_write_report_captures_every_finding(tmp_path):
    findings = [{"test": f"t::{i}", "private_config": "failed", "public_fallback": "passed"}
                for i in range(28)]
    report = tmp_path / "nested" / "report.json"

    hdw.write_report(report, findings, {"diverged": 28})
    payload = json.loads(report.read_text(encoding="utf-8"))

    assert len(payload["findings"]) == 28, "report must not truncate like the console does"
    assert payload["counts"]["diverged"] == 28
    assert payload["generated_at"]


def test_main_writes_report_and_says_how_many_were_not_shown(tmp_path, monkeypatch, capsys):
    """28 findings printed as 5 with no pointer is how evidence gets lost."""
    many = {f"t::{i}": "failed" for i in range(28)}

    def fake_run_arm(path, private, report):
        return (many if private else dict.fromkeys(many, "passed"), "")

    report = tmp_path / "r.json"
    monkeypatch.setattr(hdw, "run_arm", fake_run_arm)
    monkeypatch.setattr(hdw, "write_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["h.py", "--dry-run", "--no-warmup", "--report", str(report)])

    assert hdw.main() == 1
    out = capsys.readouterr().out
    assert "… 23 more not shown" in out
    assert str(report) in out
    assert len(json.loads(report.read_text(encoding="utf-8"))["findings"]) == 28


def test_main_writes_report_on_a_clean_pass(tmp_path, monkeypatch):
    report = tmp_path / "clean.json"
    monkeypatch.setattr(hdw, "run_arm", lambda *a, **k: ({"t::a": "passed"}, ""))
    monkeypatch.setattr(hdw, "write_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["h.py", "--no-warmup", "--report", str(report)])

    assert hdw.main() == 0
    assert json.loads(report.read_text(encoding="utf-8"))["findings"] == []


def test_default_path_is_the_scope_that_is_clean_in_both_arms():
    """The full suite needs 25min and a warm-up to mean anything; the daily
    default must be the scope where the branch lives and both arms are clean."""
    assert hdw.DEFAULT_PATH == "tests/test_fylgja/"


def test_main_runs_warmup_before_the_arms(monkeypatch):
    """Without it the first arm's startup tax lands in the report as divergence."""
    calls: list[str] = []
    monkeypatch.setattr(hdw, "run_warmup", lambda path: calls.append(f"warmup:{path}"))

    def fake_run_arm(path, private, report):
        calls.append(f"arm:{private}")
        return ({"t::a": "passed"}, "")

    monkeypatch.setattr(hdw, "run_arm", fake_run_arm)
    monkeypatch.setattr(hdw, "write_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["h.py", "--path", "tests/x/"])

    assert hdw.main() == 0
    assert calls[0] == "warmup:tests/x/", "warm-up must precede both arms"
    assert calls[1:] == ["arm:True", "arm:False"]


def test_main_no_warmup_flag_skips_it(monkeypatch):
    monkeypatch.setattr(hdw, "run_warmup", lambda path: pytest.fail("--no-warmup must skip"))
    monkeypatch.setattr(hdw, "run_arm", lambda *a, **k: ({"t::a": "passed"}, ""))
    monkeypatch.setattr(hdw, "write_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["h.py", "--no-warmup"])

    assert hdw.main() == 0


def test_warmup_failure_is_not_fatal(monkeypatch, capsys):
    """A dead warm-up should make the arms noisy, not stop the pass."""
    def boom(cmd, **kwargs):
        raise OSError("no interpreter")

    monkeypatch.setattr(hdw.subprocess, "run", boom)
    hdw.run_warmup("tests/")

    assert "warm-up pass failed" in capsys.readouterr().err


def test_warmup_discards_outcomes_and_says_so(monkeypatch, capsys):
    monkeypatch.setattr(hdw.subprocess, "run", lambda cmd, **k: None)
    hdw.run_warmup("tests/")
    out = capsys.readouterr().out

    assert "warm-up pass starting" in out
    assert "outcomes discarded" in out


def test_watchdog_is_registered_in_the_loop_registry():
    """An unregistered watchdog has no heartbeat, so fleet_status cannot miss it."""
    from willow.fylgja.loops.registry import load_registry

    loops = [loop for loop in load_registry() if loop.get("id") == "host-divergence-watch"]

    assert len(loops) == 1, "host-divergence-watch missing from loops.json"
    loop = loops[0]
    assert loop["status"] == "active"
    assert loop["heartbeat"]["watchmen_key"] == "host_divergence_watch"
    assert Path(loop["task"]["ref"]).name == "host_divergence_watch.py"
