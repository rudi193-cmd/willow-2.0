"""Tests for ratatosk doctor / panic."""
from __future__ import annotations

from ratatosk.doctor import clear_panic, panic, run_doctor


def test_doctor_runs(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("RATATOSK_GROVE_TAILNET_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("GROVE_TOKEN", "tok")
    report = run_doctor()
    assert report.checks
    names = {c.name for c in report.checks}
    assert "transport" in names
    assert "panic" in names


def test_panic_creates_file(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    clear_panic()
    result = panic("test")
    assert result["panic"] is True
    report = run_doctor()
    panic_check = next(c for c in report.checks if c.name == "panic")
    assert not panic_check.ok
    clear_panic()
