"""Tests for S8/KP6b — generalized symlink-bind re-emission."""
import json
from pathlib import Path

from core.kart_sandbox import build_bwrap_argv, collect_config_symlinks


def _make_repo(tmp_path: Path, bind_entries: dict) -> Path:
    repo = tmp_path / "repo"
    cfg_dir = repo / "willow" / "fylgja" / "config"
    cfg_dir.mkdir(parents=True)
    # willow_repo_root()-shaped marker so helpers accept this root
    (repo / "core").mkdir()
    (repo / "core" / "pg_bridge.py").write_text("", encoding="utf-8")
    (cfg_dir / "kart-sandbox.json").write_text(json.dumps(bind_entries), encoding="utf-8")
    return repo


def test_config_symlink_detected(tmp_path):
    real = tmp_path / "real-store"
    real.mkdir()
    link = tmp_path / "linked-store"
    link.symlink_to(real)
    repo = _make_repo(tmp_path, {"bind_read_write": [str(link)]})
    links = collect_config_symlinks(repo)
    assert (str(real.resolve()), str(link)) in links


def test_plain_dirs_and_dangling_links_skipped(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "nope")
    repo = _make_repo(
        tmp_path, {"bind_read_only": [str(plain), str(dangling)]}
    )
    assert collect_config_symlinks(repo) == []


def test_symlink_deduped_across_tiers(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    repo = _make_repo(
        tmp_path,
        {"bind_read_only": [str(link)], "bind_try": [str(link)]},
    )
    links = collect_config_symlinks(repo)
    assert len(links) == 1


def test_bwrap_argv_emits_config_symlinks(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    repo = _make_repo(tmp_path, {"bind_read_write": [str(link)]})
    argv = build_bwrap_argv(root=repo)
    joined = list(argv)
    assert "--symlink" in joined
    idx = [i for i, a in enumerate(joined) if a == "--symlink"]
    pairs = {(joined[i + 1], joined[i + 2]) for i in idx}
    assert (str(real.resolve()), str(link)) in pairs


def test_live_config_willow_alias_still_linked():
    """On hosts where ~/.willow is a symlink, the argv must still carry it —
    via the generic pass or the alias fallback."""
    from willow.fylgja.willow_home import willow_home, willow_home_alias

    alias = willow_home_alias()
    if not alias.is_symlink():
        import pytest
        pytest.skip("~/.willow is not a symlink on this host")
    argv = build_bwrap_argv()
    idx = [i for i, a in enumerate(argv) if a == "--symlink"]
    links = {argv[i + 2] for i in idx}
    assert str(alias) in links
    assert str(willow_home()) in {argv[i + 1] for i in idx}