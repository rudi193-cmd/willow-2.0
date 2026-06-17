# willow/hns_enforcer.py — HNS Layer 3: in-flight VRAM accounting. ΔΣ=42
"""
Post-call accounting for HNS quota enforcement.

Each inference call through _try_hns acquires a VRAM slot on the target node
and releases it when the call completes. Nodes with hns_quota_gb=None are
uncapped. Nodes that are full return False from acquire() — the caller falls
through to local/cloud.

SOIL layout: hns/inflight/{node_addr}/{job_id}
  {id, model, vram_gb, active}
"""
from __future__ import annotations

import uuid

from core.store_port import StorePort
from willow.grove_coordination import node_list
from willow.hns_scheduler import _estimate_vram_gb

_INFLIGHT_COL = "hns/inflight"


def _inflight_col(node_addr: str) -> str:
    return f"{_INFLIGHT_COL}/{node_addr}"


def _sum_inflight(store: StorePort, node_addr: str) -> float:
    """Sum VRAM (GB) of all active in-flight jobs on a node."""
    records = store.list(_inflight_col(node_addr))
    return sum(r.get("vram_gb", 0.0) for r in records if r.get("active", False))


def _node_quota(store: StorePort, node_addr: str) -> float | None:
    """Return hns_quota_gb for a node, or None if uncapped."""
    for node in node_list(store):
        if node.get("addr") == node_addr:
            return node.get("2.0_stub", {}).get("hns_quota_gb")
    return None


def acquire(store: StorePort, node_addr: str, model_name: str) -> tuple[bool, str]:
    """Reserve VRAM for model_name on node_addr.

    Returns (allowed, job_id). If not allowed, job_id is empty.
    Nodes with hns_quota_gb=None are always allowed (uncapped).
    """
    needed = _estimate_vram_gb(model_name)
    quota = _node_quota(store, node_addr)

    if quota is not None:
        current = _sum_inflight(store, node_addr)
        if current + needed > quota:
            return False, ""

    job_id = str(uuid.uuid4())[:8].upper()
    store.put(_inflight_col(node_addr), {
        "id":      job_id,
        "model":   model_name,
        "vram_gb": needed,
        "active":  True,
    })
    return True, job_id


def release(store: StorePort, node_addr: str, job_id: str) -> None:
    """Mark a job complete, freeing its VRAM quota slot."""
    records = store.list(_inflight_col(node_addr))
    for r in records:
        if r.get("id") == job_id and r.get("active", False):
            store.put(_inflight_col(node_addr), {**r, "active": False})
            return
