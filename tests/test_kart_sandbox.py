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
