"""Tests for core/public_serve.py port selection."""

import pytest

from core.public_serve import DEFAULT_PUBLIC_PORT, pick_public_chat_port


def test_pick_public_chat_port_prefers_default_when_free(monkeypatch):
    monkeypatch.setattr(
        "core.public_serve.host_port_open",
        lambda host, port, timeout=0.5: False,
    )
    port, skipped = pick_public_chat_port(preferred=DEFAULT_PUBLIC_PORT)
    assert port == DEFAULT_PUBLIC_PORT
    assert skipped is None


def test_pick_public_chat_port_falls_back_when_default_busy(monkeypatch):
    busy = {DEFAULT_PUBLIC_PORT}

    def fake_open(host, port, timeout=0.5):
        return port in busy

    monkeypatch.setattr("core.public_serve.host_port_open", fake_open)
    port, skipped = pick_public_chat_port(preferred=DEFAULT_PUBLIC_PORT)
    assert port != DEFAULT_PUBLIC_PORT
    assert skipped == DEFAULT_PUBLIC_PORT


def test_pick_public_chat_port_explicit_busy_raises(monkeypatch):
    monkeypatch.setattr(
        "core.public_serve.host_port_open",
        lambda host, port, timeout=0.5: True,
    )
    with pytest.raises(OSError, match="already in use"):
        pick_public_chat_port(preferred=7788, explicit=True)
