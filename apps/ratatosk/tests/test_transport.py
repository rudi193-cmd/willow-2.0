"""Tests for tailnet-first transport config."""
from __future__ import annotations

import json
from pathlib import Path

from ratatosk.transport.config import load_transport_config, save_transport_config


def test_tailnet_default(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("GROVE_URL", raising=False)
    monkeypatch.setenv("RATATOSK_TRANSPORT", "tailnet")
    monkeypatch.setenv("RATATOSK_GROVE_TAILNET_URL", "http://100.64.0.5:8787")
    monkeypatch.setenv("GROVE_TOKEN", "test-token")
    cfg = load_transport_config()
    assert cfg.mode == "tailnet"
    assert cfg.grove_url == "http://100.64.0.5:8787"
    assert cfg.grove_token == "test-token"
    assert not cfg.public_exposure


def test_public_relay_requires_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("RATATOSK_TRANSPORT", "ngrok")
    monkeypatch.setenv("RATATOSK_GROVE_NGROK_URL", "https://example.ngrok.app")
    monkeypatch.setenv("GROVE_TOKEN", "tok")
    cfg = load_transport_config()
    issues = cfg.issues()
    assert any("public relay" in i for i in issues)


def test_save_config_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("RATATOSK_GROVE_TAILNET_URL", "http://100.1.1.1:9")
    monkeypatch.setenv("GROVE_TOKEN", "abc")
    cfg = load_transport_config()
    path = save_transport_config(cfg)
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["transport"] == "tailnet"
