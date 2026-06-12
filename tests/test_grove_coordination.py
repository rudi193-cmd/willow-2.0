"""tests/test_grove_coordination.py"""
import pytest
from unittest.mock import patch
from core.willow_store import WillowStore
from willow.grove_coordination import (
    outbox_queue, outbox_drain, node_announce, node_list,
    _query_ollama_models,
)


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path))
    return WillowStore()


def test_outbox_queue_and_drain(store):
    msg_id = outbox_queue(store, "felix@laptop:8550", "ALERT", {"type": "test"})
    assert msg_id
    msgs = outbox_drain(store, "felix@laptop:8550")
    assert len(msgs) == 1
    assert msgs[0]["type"] == "ALERT"
    # Second drain returns nothing (already delivered)
    assert outbox_drain(store, "felix@laptop:8550") == []


def test_node_announce_and_list(store):
    node_announce(store, "felix@laptop:8550", "Felix", "1.9.0")
    nodes = node_list(store)
    addrs = [n["addr"] for n in nodes]
    assert "felix@laptop:8550" in addrs


def test_node_has_2_0_stub(store):
    with patch("willow.grove_coordination._query_ollama_models", return_value=[]):
        node_announce(store, "test@host:8550", "Test", "1.9.0")
    nodes = node_list(store)
    node = next(n for n in nodes if n["addr"] == "test@host:8550")
    assert "2.0_stub" in node
    stub = node["2.0_stub"]
    assert stub["hns_opt_in"] is None
    assert stub["hns_quota_gb"] is None
    assert stub["cpu_cores"] is not None
    assert stub["cpu_cores"] >= 1
    assert stub["models_loaded"] == []


def test_node_announce_hns_params(store):
    node_announce(store, "gpu@host:8550", "GPU Node", "2.0.0", hns_opt_in=True, hns_quota_gb=4.0)
    node = next(n for n in node_list(store) if n["addr"] == "gpu@host:8550")
    assert node["2.0_stub"]["hns_opt_in"] is True
    assert node["2.0_stub"]["hns_quota_gb"] == 4.0


def test_node_announce_preserves_hns_on_reannounce(store):
    node_announce(store, "gpu@host:8550", "GPU Node", "2.0.0", hns_opt_in=True, hns_quota_gb=4.0)
    node_announce(store, "gpu@host:8550", "GPU Node", "2.0.0")
    node = next(n for n in node_list(store) if n["addr"] == "gpu@host:8550")
    assert node["2.0_stub"]["hns_opt_in"] is True
    assert node["2.0_stub"]["hns_quota_gb"] == 4.0


def test_query_ollama_models_returns_empty_on_error():
    # No Ollama in CI — must return [] without raising.
    with patch("urllib.request.urlopen", side_effect=OSError("refused")):
        assert _query_ollama_models() == []


def test_query_ollama_models_parses_tags_response():
    import json
    from unittest.mock import MagicMock
    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps(
        {"models": [{"name": "llama3.1:8b"}, {"name": "mistral:7b"}]}
    ).encode()
    fake_resp.__enter__ = lambda s: s
    fake_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=fake_resp):
        models = _query_ollama_models()
    assert models == ["llama3.1:8b", "mistral:7b"]


def test_node_announce_populates_models_loaded(store):
    with patch(
        "willow.grove_coordination._query_ollama_models",
        return_value=["llama3.1:8b"],
    ):
        node_announce(store, "local@host", "local", "2.0.0")
    node = next(n for n in node_list(store) if n["addr"] == "local@host")
    assert node["2.0_stub"]["models_loaded"] == ["llama3.1:8b"]
