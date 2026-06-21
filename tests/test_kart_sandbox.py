"""Tests for core/kart_sandbox.py — mount policy and worktree discovery."""
from pathlib import Path

import pytest

from core.kart_sandbox import (
    build_bwrap_argv,
    collect_bind_mounts,
    kart_env,
    load_sandbox_config,
    run_shell,
    run_shell_result_for_task,
    sandbox_manifest,
    task_allows_network,
    unreachable_notes,
    willow_repo_root,
)


@pytest.fixture
def repo_root():
    root = willow_repo_root()
    assert root is not None
    return root


def test_sandbox_config_loads(repo_root):
    cfg = load_sandbox_config(repo_root)
    assert "bind_read_write" in cfg
    assert "{{WILLOW_ROOT}}" in cfg["bind_read_write"][0]


def test_collect_bind_mounts_includes_repo_and_worktrees(repo_root):
    wt = repo_root / "worktrees" / "_kart_test_wt"
    wt.mkdir(parents=True, exist_ok=True)
    try:
        mounts = collect_bind_mounts(repo_root)
        hosts = {str(h) for h, _, _ in mounts}
        assert str(repo_root.resolve()) in hosts
        assert str(wt.resolve()) in hosts
    finally:
        wt.rmdir()


def test_collect_bind_mounts_resolves_worktree_symlink(repo_root, tmp_path):
    external = tmp_path / "external-wt"
    external.mkdir()
    link = repo_root / "worktrees" / "_kart_symlink_wt"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(external)
    try:
        mounts = collect_bind_mounts(repo_root)
        hosts = {str(h) for h, _, _ in mounts}
        assert str(external.resolve()) in hosts
    finally:
        link.unlink()


def test_build_bwrap_argv_has_core_flags(repo_root):
    argv = build_bwrap_argv(allow_net=False, root=repo_root)
    assert argv[0] == "bwrap"
    assert "--unshare-net" in argv
    assert "--die-with-parent" in argv
    assert any(str(repo_root.resolve()) in arg for arg in argv)


def test_task_allows_network_directive():
    assert task_allows_network("python3 /tmp/x.py\n# allow_net\n")
    assert not task_allows_network("python3 /tmp/x.py")


def test_run_shell_echo(repo_root, monkeypatch):
    monkeypatch.setenv("WILLOW_KART_NO_BWRAP", "1")
    out = run_shell("echo kart-sandbox-ok", timeout=10)
    assert out["returncode"] == 0
    assert "kart-sandbox-ok" in out["stdout"]
    assert out["sandbox"] == "plain"


def test_kart_env_repo_root_wins_over_stale_env(repo_root, monkeypatch):
    monkeypatch.setenv("WILLOW_ROOT", str(Path.home()))
    env = kart_env(repo_root)
    assert env["WILLOW_ROOT"] == str(repo_root.resolve())
    assert env["PYTHONPATH"] == str(repo_root.resolve())


def test_kart_env_sets_willow_in_kart(repo_root):
    env = kart_env(repo_root)
    assert env.get("WILLOW_IN_KART") == "1"


# ── Phase 0 — KP1 bind hardening (S1, S4, GAP-A) ──────────────────────────────

def _mount_map(repo_root):
    """host(str) -> read_only(bool) for every bind."""
    return {str(h): ro for h, _, ro in collect_bind_mounts(repo_root)}


def test_kp1_ssh_dir_never_bound(repo_root):
    """S1: ~/.ssh (private keys) must not be a bind at all."""
    ssh_dir = str((Path.home() / ".ssh").resolve())
    assert ssh_dir not in _mount_map(repo_root)


def test_kp1_github_is_read_only(repo_root):
    """S4/GAP-A: ~/github defaults to read-only (WILLOW_ROOT nests rw on top)."""
    gh = Path.home() / "github"
    if not gh.exists():
        pytest.skip("~/github absent on this host")
    mounts = _mount_map(repo_root)
    assert mounts.get(str(gh.resolve())) is True


def test_kp1_willow_root_is_read_write_under_github(repo_root):
    """WILLOW_ROOT (under the now-ro ~/github) must still be read-write."""
    mounts = _mount_map(repo_root)
    assert mounts.get(str(repo_root.resolve())) is False


def test_kp1_systemd_config_not_writable(repo_root):
    """GAP-A: ~/.config/systemd must not be read-write (no unit persistence)."""
    sd = Path.home() / ".config" / "systemd"
    if not sd.exists():
        pytest.skip("~/.config/systemd absent on this host")
    assert _mount_map(repo_root).get(str(sd.resolve())) is True


def test_kp1_tmp_not_a_host_bind(repo_root):
    """S11: /tmp is a private tmpfs, not a host bind."""
    assert "/tmp" not in _mount_map(repo_root)


# ── Phase 0 — KP2 namespace + kernel-surface hardening (S2, S11–S14, S16) ─────

def test_kp2_hardening_flags_present(repo_root):
    argv = build_bwrap_argv(allow_net=False, root=repo_root)
    for flag in ("--new-session", "--unshare-ipc", "--unshare-uts", "--as-pid-1", "--unshare-pid"):
        assert flag in argv, f"missing {flag}"


def test_kp2_tmpfs_scratch(repo_root):
    argv = build_bwrap_argv(allow_net=False, root=repo_root)
    pairs = list(zip(argv, argv[1:]))
    assert ("--tmpfs", "/tmp") in pairs
    assert ("--tmpfs", "/dev/shm") in pairs


# ── Phase 0 — GAP-B credential gating + GAP-C ssh ─────────────────────────────

def test_gapb_credentials_stripped_without_net(repo_root, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-a")
    monkeypatch.setenv("GITHUB_TOKEN", "secret-g")
    env = kart_env(repo_root, allow_net=False)
    assert "ANTHROPIC_API_KEY" not in env
    assert "GITHUB_TOKEN" not in env


def test_gapb_credentials_present_with_net(repo_root, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-a")
    env = kart_env(repo_root, allow_net=True)
    assert env.get("ANTHROPIC_API_KEY") == "secret-a"


def test_gapc_ssh_keys_not_bound_even_with_net(repo_root):
    """GAP-C: even on a network task, the ~/.ssh dir is never bound — only
    known_hosts (a file) may appear. Private keys never enter the sandbox."""
    argv = build_bwrap_argv(allow_net=True, root=repo_root)
    ssh_dir = str((Path.home() / ".ssh").resolve())
    # the bare ~/.ssh directory must not be a bind target
    assert ssh_dir not in argv


# ── Phase 1 — KP3 boundary manifest (S3, S5, S6, S7, S15) ─────────────────────

def test_kp3_manifest_shape(repo_root):
    m = sandbox_manifest(allow_net=False, root=repo_root)
    for key in ("engine", "allow_net", "bound_rw", "bound_ro", "tmpfs", "path_dirs"):
        assert key in m, f"manifest missing {key}"
    # WILLOW_ROOT is read-write; ~/github (if present) is read-only.
    assert str(repo_root.resolve()) in m["bound_rw"]
    if m["engine"] == "bwrap":
        assert "/tmp" in m["tmpfs"]


def test_kp3_unreachable_note_for_unbound_home_path(repo_root):
    m = sandbox_manifest(allow_net=False, root=repo_root)
    if m["engine"] != "bwrap":
        pytest.skip("manifest notes only apply under bwrap")
    home = str(Path.home())
    # ~/.claude root stays unbound (only ~/.claude/projects is a KP4 bind),
    # so a path directly under it is the stable unreachable probe.
    notes = unreachable_notes(f"cat {home}/.claude/x.jsonl", m)
    assert any(".claude" in n for n in notes)


# ── Phase 2 — KP4 transcript stores ro (S5) ───────────────────────────────────

def test_kp4_transcript_stores_in_optional_ro_config(repo_root):
    cfg = load_sandbox_config(repo_root)
    optional_ro = cfg.get("bind_try_read_only", [])
    assert "{{HOME}}/.claude/projects" in optional_ro
    assert "{{HOME}}/.cursor" in optional_ro
    # the credential-bearing ~/.claude root must not appear in any bind list
    for key in ("bind_read_only", "bind_read_write", "bind_try", "bind_try_read_only"):
        assert "{{HOME}}/.claude" not in cfg.get(key, [])


def test_kp4_transcript_mounts_read_only_when_present(repo_root):
    mounts = {str(h): ro for h, _c, ro in collect_bind_mounts(repo_root)}
    for rel in (".claude/projects", ".cursor"):
        host = str((Path.home() / rel).resolve())
        if host in mounts:
            assert mounts[host] is True, f"{host} must be read-only"


def test_kp3_no_note_for_bound_path(repo_root):
    m = sandbox_manifest(allow_net=False, root=repo_root)
    notes = unreachable_notes(f"ls {repo_root}/core", m)
    assert notes == []


def test_operator_promoted_rw_project_roots(repo_root):
    """DispatchesFromReality + safe-app-store-public are Kart RW when present."""
    if sandbox_manifest(allow_net=False, root=repo_root)["engine"] != "bwrap":
        pytest.skip("bwrap not active")
    home = Path.home()
    promoted = (
        home / "github" / "DispatchesFromReality",
        home / "github" / "safe-app-store-public",
    )
    mounts = {str(h): ro for h, _c, ro in collect_bind_mounts(repo_root)}
    for path in promoted:
        if not path.is_dir():
            continue
        key = str(path.resolve())
        assert key in mounts, f"missing bind for {key}"
        assert mounts[key] is False, f"{key} must be read-write"

def test_kp3_result_carries_manifest(monkeypatch):
    monkeypatch.setenv("WILLOW_KART_NO_BWRAP", "1")
    status, result = run_shell_result_for_task("echo manifest-ok", timeout=10)
    assert status == "completed"
    assert "sandbox_manifest" in result
    assert result["sandbox_manifest"]["engine"] == "plain"


# ── Phase 1 — KP5 PATH completeness (S6) ──────────────────────────────────────

def test_kp5_local_bin_on_path(repo_root):
    env = kart_env(repo_root)
    path_parts = env["PATH"].split(":")
    assert str(Path.home() / ".local" / "bin") in path_parts


# ── Uniform error capture — every failure carries a readable `error` ──────────

def test_uniform_error_on_exit_code_with_no_output(monkeypatch):
    """A command that fails by exit code with no stderr/stdout still records a
    non-empty `error` instead of a causeless failure."""
    monkeypatch.setenv("WILLOW_KART_NO_BWRAP", "1")
    status, result = run_shell_result_for_task(
        "python3 -c 'import sys; sys.exit(3)'", timeout=10
    )
    assert status == "failed"
    assert result["stderr"] == ""
    assert result["error"] == "exited 3 with no output"


def test_uniform_error_falls_back_to_stdout_tail(monkeypatch):
    """When a failing command wrote only to stdout, `error` summarizes it."""
    monkeypatch.setenv("WILLOW_KART_NO_BWRAP", "1")
    status, result = run_shell_result_for_task(
        "python3 -c 'print(\"boom\"); import sys; sys.exit(2)'", timeout=10
    )
    assert status == "failed"
    assert result["error"] == "exited 2: boom"


def test_uniform_error_prefers_real_stderr(monkeypatch):
    """A genuine stderr message wins over the synthesized exit-code summary."""
    monkeypatch.setenv("WILLOW_KART_NO_BWRAP", "1")
    status, result = run_shell_result_for_task(
        "python3 -c 'import sys; sys.stderr.write(\"kaboom\\n\"); sys.exit(1)'",
        timeout=10,
    )
    assert status == "failed"
    assert result["error"] == "kaboom"


def test_uniform_error_absent_on_success(monkeypatch):
    """Successful tasks carry no error field."""
    monkeypatch.setenv("WILLOW_KART_NO_BWRAP", "1")
    status, result = run_shell_result_for_task("echo ok", timeout=10)
    assert status == "completed"
    assert "error" not in result
