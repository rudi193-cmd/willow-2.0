"""Policy tests for Kart sandbox bind exposure — operator vault must stay unbound."""

from pathlib import Path

import pytest

from core.kart_sandbox import collect_bind_mounts, load_sandbox_config, willow_repo_root

_BIND_LIST_KEYS = (
    "bind_read_only",
    "bind_read_write",
    "bind_try",
    "bind_try_read_only",
)
_VAULT_FRAGMENT = "sean-data-vault"


@pytest.fixture
def repo_root():
    root = willow_repo_root()
    assert root is not None
    return root


def _paths_from_config(cfg: dict) -> list[str]:
    paths: list[str] = []
    for key in _BIND_LIST_KEYS:
        paths.extend(str(p) for p in cfg.get(key, []))
    return paths


def test_operator_vault_not_in_sandbox_bind_config(repo_root):
    cfg = load_sandbox_config(repo_root)
    offenders = [p for p in _paths_from_config(cfg) if _VAULT_FRAGMENT in p]
    assert offenders == [], f"vault path in sandbox config bind lists: {offenders}"


def test_operator_vault_not_in_collect_bind_mounts(repo_root):
    mounts = collect_bind_mounts(repo_root)
    offenders = [
        str(host)
        for host, _container, _read_only in mounts
        if _VAULT_FRAGMENT in str(host)
    ]
    assert offenders == [], f"vault path mounted into sandbox: {offenders}"
