"""Tests for core/kart_sandbox.py — mount policy and worktree discovery."""
from pathlib import Path

import pytest

from core.kart_sandbox import (
    build_bwrap_argv,
    collect_bind_mounts,
    kart_env,
    load_sandbox_config,
    run_shell,
    task_allows_network,
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
