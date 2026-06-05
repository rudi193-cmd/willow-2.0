"""tests/test_hns_enforcer.py — HNS Layer 3 enforcement tests."""
import pytest
from unittest.mock import patch
from core.willow_store import WillowStore
from willow.grove_coordination import node_announce
from willow.hns_enforcer import acquire, release, _sum_inflight


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path))
    return WillowStore()


@pytest.fixture
def capped_node(store):
    """A node opted-in with 6 GB quota."""
    with patch("willow.grove_coordination._detect_gpu_info", return_value=("RTX4090", 24.0)), \
         patch("willow.grove_coordination._query_ollama_models", return_value=[]):
        node_announce(store, "node-a", "A", "2.0.0", hns_opt_in=True, hns_quota_gb=6.0)
    return store


@pytest.fixture
def uncapped_node(store):
    """A node opted-in with no quota limit."""
    with patch("willow.grove_coordination._detect_gpu_info", return_value=("RTX4090", 24.0)), \
         patch("willow.grove_coordination._query_ollama_models", return_value=[]):
        node_announce(store, "node-b", "B", "2.0.0", hns_opt_in=True)
    return store


# ── acquire ───────────────────────────────────────────────────────────────────

def test_acquire_uncapped_always_allowed(uncapped_node):
    allowed, job_id = acquire(uncapped_node, "node-b", "llama3.1:8b")
    assert allowed is True
    assert job_id != ""


def test_acquire_within_quota(capped_node):
    # 6 GB quota, llama3.2:3b needs 2 GB — should allow
    allowed, job_id = acquire(capped_node, "node-a", "llama3.2:3b")
    assert allowed is True
    assert job_id != ""


def test_acquire_denied_when_quota_full(capped_node):
    # Fill 6 GB quota with two 3b jobs (2 GB each = 4 GB)
    acquire(capped_node, "node-a", "llama3.2:3b")
    acquire(capped_node, "node-a", "llama3.2:3b")
    # Third job needs 5.5 GB — total would be 9.5 GB > 6 GB quota
    allowed, job_id = acquire(capped_node, "node-a", "llama3.1:8b")
    assert allowed is False
    assert job_id == ""


def test_acquire_denied_single_oversized_model(capped_node):
    # llama3.1:8b needs 5.5 GB — within 6 GB quota alone
    allowed, _ = acquire(capped_node, "node-a", "llama3.1:8b")
    assert allowed is True
    # Second 8b job would push to 11 GB > 6 GB
    allowed2, _ = acquire(capped_node, "node-a", "llama3.1:8b")
    assert allowed2 is False


# ── release ───────────────────────────────────────────────────────────────────

def test_release_frees_quota(capped_node):
    # Fill quota
    _, job1 = acquire(capped_node, "node-a", "llama3.1:8b")  # 5.5 GB
    assert _sum_inflight(capped_node, "node-a") == pytest.approx(5.5)

    # Release it
    release(capped_node, "node-a", job1)
    assert _sum_inflight(capped_node, "node-a") == pytest.approx(0.0)

    # Now another 8b job should be allowed
    allowed, _ = acquire(capped_node, "node-a", "llama3.1:8b")
    assert allowed is True


def test_release_unknown_job_is_safe(capped_node):
    """release() on a non-existent job_id must not raise."""
    release(capped_node, "node-a", "DEADBEEF")


# ── sum_inflight ──────────────────────────────────────────────────────────────

def test_sum_inflight_empty(store):
    assert _sum_inflight(store, "nobody") == 0.0


def test_sum_inflight_counts_only_active(capped_node):
    _, job1 = acquire(capped_node, "node-a", "llama3.2:3b")  # 2 GB active
    _, job2 = acquire(capped_node, "node-a", "llama3.2:3b")  # 2 GB active
    assert _sum_inflight(capped_node, "node-a") == pytest.approx(4.0)
    release(capped_node, "node-a", job1)
    assert _sum_inflight(capped_node, "node-a") == pytest.approx(2.0)
