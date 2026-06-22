from __future__ import annotations

from pathlib import Path

import pytest

from willow.fylgja.fleet_venv import (
    check_fleet_venv,
    fleet_venv,
    sync_fleet_venv,
    venv_is_usable,
)


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _make_fake_venv(venv: Path, *, usable: bool) -> None:
    bin_dir = venv / "bin"
    bin_dir.mkdir(parents=True)
    if usable:
        script = (
            "#!/bin/sh\n"
            'if [ "$1" = "-c" ] && echo "$2" | grep -q "import mcp"; then exit 0; fi\n'
            "exit 1\n"
        )
    else:
        script = "#!/bin/sh\nexit 1\n"
    _write_executable(bin_dir / "python3", script)


def test_venv_is_usable_detects_stub(tmp_path: Path) -> None:
    good = tmp_path / "good"
    bad = tmp_path / "bad"
    _make_fake_venv(good, usable=True)
    _make_fake_venv(bad, usable=False)
    assert venv_is_usable(good) is True
    assert venv_is_usable(bad) is False


def test_sync_fleet_venv_replaces_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "willow-2.0"
    home = tmp_path / ".willow"
    root.mkdir()
    home.mkdir()
    monkeypatch.setenv("WILLOW_HOME", str(home))

    _make_fake_venv(root / ".venv-dev", usable=True)
    _make_fake_venv(home / "venv", usable=False)

    status = sync_fleet_venv(root)
    link = fleet_venv(root)

    assert status.ok is True
    assert link.is_symlink()
    assert link.resolve() == (root / ".venv-dev").resolve()
    assert check_fleet_venv(root).ok is True


def test_sync_fleet_venv_noop_when_already_linked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "willow-2.0"
    home = tmp_path / ".willow"
    root.mkdir()
    home.mkdir()
    monkeypatch.setenv("WILLOW_HOME", str(home))

    dev = root / ".venv-dev"
    _make_fake_venv(dev, usable=True)
    (home / "venv").symlink_to(dev, target_is_directory=True)

    before = check_fleet_venv(root)
    after = sync_fleet_venv(root)

    assert before.ok is True
    assert after.ok is True
    assert "already" in after.detail or "symlink" in after.detail


def test_check_fleet_venv_reports_missing_dev(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "willow-2.0"
    home = tmp_path / ".willow"
    root.mkdir()
    home.mkdir()
    monkeypatch.setenv("WILLOW_HOME", str(home))

    status = check_fleet_venv(root)

    assert status.ok is False
    assert "missing dev venv" in status.detail
