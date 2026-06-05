"""tests/test_hns_scheduler.py — HNS Layer 2 scheduler tests."""
import pytest
from unittest.mock import patch
from core.willow_store import WillowStore
from willow.hns_scheduler import _estimate_vram_gb, select_node
from willow.grove_coordination import node_announce


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path))
    return WillowStore()


# ── _estimate_vram_gb ─────────────────────────────────────────────────────────

def test_estimate_known_model():
    assert _estimate_vram_gb("llama3.1:8b") == 5.5

def test_estimate_known_70b():
    assert _estimate_vram_gb("llama3.3:70b") == 42.0

def test_estimate_size_hint_fallback():
    assert _estimate_vram_gb("some-custom:13b-chat") == 8.0

def test_estimate_default_fallback():
    assert _estimate_vram_gb("unknown-model:latest") == 4.0


# ── select_node ───────────────────────────────────────────────────────────────

def test_select_no_nodes(store):
    assert select_node(store, "llama3.1:8b") is None


def test_select_node_not_opted_in(store):
    with patch("willow.grove_coordination._query_ollama_models", return_value=[]):
        node_announce(store, "host-a", "A", "2.0.0", hns_opt_in=False)
    assert select_node(store, "llama3.1:8b") is None


def test_select_node_insufficient_vram(store):
    with patch("willow.grove_coordination._detect_gpu_info", return_value=("RTX3060", 4.0)), \
         patch("willow.grove_coordination._query_ollama_models", return_value=[]):
        node_announce(store, "low-vram", "LowVRAM", "2.0.0", hns_opt_in=True)
    # 4 GB node can't run llama3.1:8b (needs 5.5 GB)
    assert select_node(store, "llama3.1:8b") is None


def test_select_node_qualifies(store):
    with patch("willow.grove_coordination._detect_gpu_info", return_value=("RTX4090", 24.0)), \
         patch("willow.grove_coordination._query_ollama_models", return_value=["llama3.1:8b"]):
        node_announce(store, "gpu-node", "GPU", "2.0.0", hns_opt_in=True)
    node = select_node(store, "llama3.1:8b")
    assert node is not None
    assert node["addr"] == "gpu-node"


def test_select_node_quota_blocks(store):
    with patch("willow.grove_coordination._detect_gpu_info", return_value=("RTX4090", 24.0)), \
         patch("willow.grove_coordination._query_ollama_models", return_value=[]):
        node_announce(store, "quota-node", "QuotaNode", "2.0.0", hns_opt_in=True, hns_quota_gb=2.0)
    # quota only allows 2 GB, llama3.1:8b needs 5.5
    assert select_node(store, "llama3.1:8b") is None


def test_select_node_prefers_most_vram(store):
    with patch("willow.grove_coordination._detect_gpu_info", return_value=("RTX4090", 24.0)), \
         patch("willow.grove_coordination._query_ollama_models", return_value=[]):
        node_announce(store, "big", "Big", "2.0.0", hns_opt_in=True)
    with patch("willow.grove_coordination._detect_gpu_info", return_value=("RTX3090", 16.0)), \
         patch("willow.grove_coordination._query_ollama_models", return_value=[]):
        node_announce(store, "small", "Small", "2.0.0", hns_opt_in=True)
    node = select_node(store, "llama3.2:3b")
    assert node["addr"] == "big"


def test_node_announce_stores_ollama_url(store, monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://192.168.1.5:11434")
    with patch("willow.grove_coordination._query_ollama_models", return_value=[]):
        node_announce(store, "remote", "Remote", "2.0.0")
    from willow.grove_coordination import node_list
    node = next(n for n in node_list(store) if n["addr"] == "remote")
    assert node["2.0_stub"]["ollama_url"] == "http://192.168.1.5:11434"
