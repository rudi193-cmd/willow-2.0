"""Tests for UTETY chat root resolution."""

from pathlib import Path

import pytest

from sap.core.utety_paths import resolve_utety_chat_root


@pytest.mark.unit
def test_resolve_utety_chat_root_finds_monorepo_app():
    repo = Path(__file__).resolve().parents[1]
    home_store = Path.home() / "safe-app-store" / "apps" / "utety-chat"
    if not (home_store / "persona_compiler.py").is_file():
        pytest.skip("utety-chat not installed at ~/safe-app-store/apps/utety-chat")

    root = resolve_utety_chat_root(repo)
    assert root is not None
    assert (root / "persona_compiler.py").is_file() or (root / "personas.py").is_file()


@pytest.mark.unit
def test_resolve_utety_chat_root_env_override(tmp_path):
    fake = tmp_path / "utety-chat"
    fake.mkdir()
    (fake / "personas.py").write_text('PERSONAS = {"Oakenscroll": "test"}\n', encoding="utf-8")

    import os

    old = os.environ.get("WILLOW_UTETY_ROOT")
    os.environ["WILLOW_UTETY_ROOT"] = str(fake)
    try:
        assert resolve_utety_chat_root() == fake.resolve()
    finally:
        if old is None:
            os.environ.pop("WILLOW_UTETY_ROOT", None)
        else:
            os.environ["WILLOW_UTETY_ROOT"] = old
