"""Tests for desktop listener capability gate."""
from __future__ import annotations

from unittest.mock import MagicMock

from ratatosk.listener import DesktopListener
from ratatosk.protocol.envelope import Intent, build_envelope, clear_nonce_cache


def test_listener_rejects_wrong_node():
    clear_nonce_cache()
    grove = MagicMock()
    grove.config.agent_name = "ratatosk"
    grove.get_history.return_value = [
        {
            "id": 1,
            "sender": "phone",
            "content": build_envelope(to="loki", prompt="hi").to_json(),
        }
    ]
    listener = DesktopListener(node="ratatosk", grove=grove)
    out = listener.run_once()
    assert out
    assert "rejected" in out[0]


def test_listener_chat_executes(monkeypatch):
    clear_nonce_cache()
    monkeypatch.setattr("ratatosk.ollama.is_available", lambda: True)
    monkeypatch.setattr("ratatosk.ollama.generate", lambda prompt, stream=False: "pong")

    grove = MagicMock()
    grove.config.agent_name = "ratatosk"
    grove.config.mode = "tailnet"
    grove.config.public_exposure = False
    grove.ping.return_value = (True, "ok")
    env = build_envelope(to="ratatosk", prompt="hello", intent=Intent.CHAT.value)
    grove.get_history.return_value = [{"id": 2, "sender": "phone", "content": env.to_json()}]

    listener = DesktopListener(node="ratatosk", grove=grove)
    out = listener.run_once()
    assert out == ["pong"]
    grove.post.assert_called()
