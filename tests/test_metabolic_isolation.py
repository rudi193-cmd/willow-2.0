"""Effect test: norn_pass survives a failing opening pass.

Guards the magma-layer class: one Postgres hiccup in compost/community/
heartbeat must not abort the whole nightly run — later passes still execute
and the failure is recorded in the report instead of vanishing.
"""
from core import metabolic


def _boom(*args, **kwargs):
    raise RuntimeError("simulated pg outage")


def test_norn_pass_isolates_opening_pass_failures(monkeypatch):
    monkeypatch.setattr(metabolic, "compost_pass", _boom)
    monkeypatch.setattr(metabolic, "community_pass", _boom)
    monkeypatch.setattr(metabolic, "measure_heartbeat", _boom)
    monkeypatch.setattr(metabolic, "demote_stale_pass", _boom)

    # dry_run=True keeps the later intelligence/promote stages inert; the
    # point under test is that all four opening failures are contained.
    report = metabolic.norn_pass(dry_run=True)

    assert set(report["pass_errors"]) == {
        "compost", "community", "heartbeat", "demote_stale"
    }
    assert all("simulated pg outage" in v for v in report["pass_errors"].values())
    # Defaults survive so the report schema stays intact for consumers.
    assert report["composted"] == 0
    assert report["communities"] == 0
    assert report["heartbeat"] == 0.5
    assert report["demoted"] == 0


def test_norn_pass_reports_empty_errors_when_clean(monkeypatch):
    monkeypatch.setattr(metabolic, "compost_pass", lambda dry_run=False: 3)
    monkeypatch.setattr(metabolic, "community_pass", lambda dry_run=False: 2)
    monkeypatch.setattr(metabolic, "measure_heartbeat", lambda: 0.7)
    monkeypatch.setattr(metabolic, "demote_stale_pass", lambda dry_run=False: 1)

    report = metabolic.norn_pass(dry_run=True)

    assert report["pass_errors"] == {}
    assert report["composted"] == 3
    assert report["communities"] == 2
    assert report["heartbeat"] == 0.7
    assert report["demoted"] == 1
