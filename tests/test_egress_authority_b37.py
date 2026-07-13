"""B-37 regression — the executor must not honor `# allow_net` without authority.

Before this fix, `core/kart_execute.run_shell_task` parsed `# allow_net` from the
task string and passed it straight to the sandbox: any submitter reaching the
shared queue got egress (verified live: task 2E8E5FE0). These tests pin the fix:

  * `egress_authority.net_authorized` requires ALL THREE keys, fail-closed on each.
  * `run_shell_task` ANDs the directive with the resolved authority, so an
    unauthorized `# allow_net` runs network-isolated and is stamped `net_denied`.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from core import egress_authority as ea
from core import kart_execute as ke


# ── fixtures: a self-contained trust root the test fully controls ──────────────

def _iso(dt: datetime) -> str:
    return dt.isoformat()


@pytest.fixture
def trust_root(tmp_path, monkeypatch):
    """Point egress_authority at a tmp trust root and return helpers to populate it."""
    apps = tmp_path / "mcp_apps"
    leases = apps / "_net_leases"
    leases.mkdir(parents=True)
    settings = tmp_path / "settings.global.json"

    monkeypatch.setenv("WILLOW_MCP_APPS_ROOT", str(apps))
    monkeypatch.setenv("WILLOW_SETTINGS_GLOBAL", str(settings))
    # keep WILLOW_HOME from leaking the real host root into path resolution
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))

    def set_consent(internet: bool):
        settings.write_text(json.dumps({"consent": {"internet": internet}}), encoding="utf-8")

    def set_manifest(app: str, perms: list[str]):
        d = apps / app
        d.mkdir(parents=True, exist_ok=True)
        (d / "manifest.json").write_text(
            json.dumps({"app_id": app, "permissions": perms}), encoding="utf-8"
        )

    def set_lease(app: str, *, ttl_seconds=1800, expires_in_seconds=1800, app_id=None):
        rec = {
            "app_id": app_id if app_id is not None else app,
            "granted_at": _iso(datetime.now(timezone.utc)),
            "expires_at": _iso(datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)),
            "ttl_seconds": ttl_seconds,
            "issuer": "test",
        }
        (leases / f"{app}.json").write_text(json.dumps(rec), encoding="utf-8")

    return type("TR", (), {
        "set_consent": staticmethod(set_consent),
        "set_manifest": staticmethod(set_manifest),
        "set_lease": staticmethod(set_lease),
    })


def _authorize_fully(tr, app="hanuman"):
    tr.set_consent(True)
    tr.set_manifest(app, ["task_queue", "task_net"])
    tr.set_lease(app)
    return app


# ── the resolver ───────────────────────────────────────────────────────────────

def test_all_three_keys_grants(trust_root):
    app = _authorize_fully(trust_root)
    ok, reason = ea.net_authorized(app)
    assert ok is True, reason


def test_no_lease_denies(trust_root):
    """The core B-37 case: capability + consent present, but no lease → deny."""
    trust_root.set_consent(True)
    trust_root.set_manifest("hanuman", ["task_net"])
    # no lease written
    ok, reason = ea.net_authorized("hanuman")
    assert ok is False
    assert "lease" in reason


def test_expired_lease_denies(trust_root):
    trust_root.set_consent(True)
    trust_root.set_manifest("hanuman", ["task_net"])
    trust_root.set_lease("hanuman", expires_in_seconds=-60)
    ok, _ = ea.net_authorized("hanuman")
    assert ok is False


def test_missing_capability_denies(trust_root):
    trust_root.set_consent(True)
    trust_root.set_manifest("hanuman", ["task_queue"])  # no task_net
    trust_root.set_lease("hanuman")
    ok, reason = ea.net_authorized("hanuman")
    assert ok is False
    assert "task_net" in reason


def test_full_access_does_not_grant_net(trust_root):
    """full_access must NOT stand in for task_net — matches the submitter's gate."""
    trust_root.set_consent(True)
    trust_root.set_manifest("hanuman", ["full_access"])
    trust_root.set_lease("hanuman")
    ok, _ = ea.net_authorized("hanuman")
    assert ok is False


def test_consent_off_denies(trust_root):
    trust_root.set_consent(False)
    trust_root.set_manifest("hanuman", ["task_net"])
    trust_root.set_lease("hanuman")
    ok, reason = ea.net_authorized("hanuman")
    assert ok is False
    assert "consent" in reason


def test_lease_app_id_mismatch_denies(trust_root):
    """A lease file whose body claims a different app_id grants nothing."""
    trust_root.set_consent(True)
    trust_root.set_manifest("hanuman", ["task_net"])
    trust_root.set_lease("hanuman", app_id="someone_else")
    ok, _ = ea.net_authorized("hanuman")
    assert ok is False


def test_empty_submitter_denies(trust_root):
    assert ea.net_authorized("")[0] is False


def test_path_traversal_submitter_denies(trust_root):
    assert ea.net_authorized("../../etc")[0] is False


# ── the executor ANDs the directive with authority ─────────────────────────────

@pytest.fixture
def capture_allow_net(monkeypatch):
    """Replace the sandbox call so we observe the allow_net the executor decided on,
    without spawning bwrap."""
    seen = {}

    def fake_run_one_shell(cmd, *, timeout, allow_net, allow_localhost):
        seen["allow_net"] = allow_net
        seen["cmd"] = cmd
        return "completed", {"returncode": 0, "stdout": "", "stderr": "", "provider": "shell"}

    monkeypatch.setattr(ke, "_run_one_shell", fake_run_one_shell)
    return seen


def test_directive_without_authority_runs_isolated(capture_allow_net):
    status, result = ke.run_shell_task(
        "echo hi\n# allow_net",
        net_authorized=False,
        net_denied_reason="no active egress lease for hanuman",
    )
    assert status == "completed"
    assert capture_allow_net["allow_net"] is False   # egress withheld
    assert result.get("net_denied") == "no active egress lease for hanuman"


def test_directive_with_authority_reaches_net(capture_allow_net):
    status, result = ke.run_shell_task(
        "echo hi\n# allow_net",
        net_authorized=True,
    )
    assert status == "completed"
    assert capture_allow_net["allow_net"] is True    # authorized → honored
    assert "net_denied" not in result


def test_no_directive_never_flags_denied(capture_allow_net):
    """A task that never asked for the net is not 'denied' — allow_net stays False,
    no net_denied noise."""
    status, result = ke.run_shell_task("echo hi", net_authorized=False)
    assert capture_allow_net["allow_net"] is False
    assert "net_denied" not in result


def test_default_is_fail_closed(capture_allow_net):
    """A caller that passes no authority at all gets no egress, directive or not."""
    ke.run_shell_task("echo hi\n# allow_net")
    assert capture_allow_net["allow_net"] is False
