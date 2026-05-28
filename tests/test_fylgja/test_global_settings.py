"""tests/test_fylgja/test_global_settings.py"""
import json
from pathlib import Path

from willow.fylgja import global_settings as gs


def test_read_consent_defaults(tmp_path: Path):
    path = tmp_path / "settings.global.json"
    consent = gs.read_consent(path=path)
    assert consent == gs.DEFAULT_CONSENT


def test_migrate_legacy_consent_json(tmp_path: Path, monkeypatch):
    legacy = tmp_path / "consent.json"
    legacy.write_text(
        json.dumps({"internet": False, "cloud_llm": True, "lan": False}),
        encoding="utf-8",
    )
    settings_path = tmp_path / "settings.global.json"
    monkeypatch.setattr(gs, "WILLOW_HOME", tmp_path)
    monkeypatch.setattr(gs, "CONSENT_LEGACY_PATH", legacy)
    data = gs.load_global_settings(path=settings_path, create=True)
    assert data["consent"]["internet"] is False
    assert data["consent"]["lan"] is False
    assert settings_path.is_file()
    assert legacy.read_text(encoding="utf-8").strip()


def test_write_consent_updates_global_and_legacy(tmp_path: Path, monkeypatch):
    settings_path = tmp_path / "settings.global.json"
    legacy = tmp_path / "consent.json"
    monkeypatch.setattr(gs, "CONSENT_LEGACY_PATH", legacy)
    gs.init_global_settings(path=settings_path, force=True)
    gs.write_consent({"internet": True, "cloud_llm": False, "lan": True}, path=settings_path)
    loaded = json.loads(settings_path.read_text(encoding="utf-8"))
    assert loaded["consent"]["cloud_llm"] is False
    legacy_data = json.loads(legacy.read_text(encoding="utf-8"))
    assert legacy_data["cloud_llm"] is False


def test_deferred_allow_net_flag_defaults(tmp_path: Path):
    settings_path = tmp_path / "settings.global.json"
    data = gs.load_global_settings(path=settings_path, create=True)
    spec = data["flags"][gs.FLAG_CONSENT_INTERNET_GATES_ALLOW_NET]
    assert spec["enabled"] is False
    assert spec["implemented"] is False
    assert spec["status"] == "deferred"
    assert gs.flag_enabled(gs.FLAG_CONSENT_INTERNET_GATES_ALLOW_NET, settings=data) is False


def test_init_global_settings_idempotent(tmp_path: Path):
    settings_path = tmp_path / "settings.global.json"
    gs.init_global_settings(path=settings_path, default_agent="hanuman")
    first = settings_path.read_text(encoding="utf-8")
    gs.init_global_settings(path=settings_path, default_agent="orin")
    second = settings_path.read_text(encoding="utf-8")
    assert first == second
