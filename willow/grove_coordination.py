# willow/grove_coordination.py — Grove coordination helpers. b17: GRVC1  ΔΣ=42
from __future__ import annotations
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from core.willow_store import WillowStore

_OUTBOX_COL  = "grove/outbox"

def _detect_gpu_info() -> tuple[str | None, float]:
    """Return (gpu_name_or_None, vram_gb). 0.0 means no GPU detected."""
    if not shutil.which("nvidia-smi"):
        return None, 0.0
    try:
        name_out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            timeout=4, text=True, stderr=subprocess.DEVNULL,
        ).strip().splitlines()
        mem_out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            timeout=4, text=True, stderr=subprocess.DEVNULL,
        ).strip().splitlines()
        gpu_name = name_out[0].strip() if name_out else None
        mib = sum(int(x.strip()) for x in mem_out if x.strip().isdigit())
        return gpu_name, round(mib / 1024, 1)
    except Exception:
        return None, 0.0


def _detect_cpu_cores() -> int:
    try:
        return os.cpu_count() or 1
    except Exception:
        return 1


_NODES_COL   = "grove/nodes"
_ALERTS_COL  = "grove/pending_alerts"


def outbox_queue(
    store: WillowStore,
    to_addr: str,
    packet_type: str,
    payload: dict,
) -> str:
    """Queue a packet for delivery when the recipient node is online."""
    msg_id = str(uuid.uuid4())[:12].upper()
    store.put(f"{_OUTBOX_COL}/{to_addr}", {
        "id":        msg_id,
        "msg_id":    msg_id,
        "to":        to_addr,
        "type":      packet_type,
        "payload":   payload,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "delivered": False,
    })
    return msg_id


def outbox_drain(store: WillowStore, to_addr: str) -> list[dict]:
    """Return all undelivered messages for a recipient and mark them delivered."""
    pending = store.list(f"{_OUTBOX_COL}/{to_addr}")
    undelivered = [r for r in pending if not r.get("delivered", False)]
    for msg in undelivered:
        msg["delivered"] = True
        store.put(f"{_OUTBOX_COL}/{to_addr}", msg)
    return undelivered


def node_announce(
    store: WillowStore,
    addr: str,
    name: str,
    willow_version: str,
    hns_opt_in: bool | None = None,
    hns_quota_gb: float | None = None,
) -> None:
    """Register or update a node in the registry with real hardware values."""
    existing = store.get(_NODES_COL, addr) or {}
    existing_stub = existing.get("2.0_stub", {})

    gpu_name, vram_gb = _detect_gpu_info()

    store.put(_NODES_COL, {
        **existing,
        "id":             addr,
        "addr":           addr,
        "name":           name,
        "willow_version": willow_version,
        "last_seen":      datetime.now(timezone.utc).isoformat(),
        "2.0_stub": {
            "gpu":           gpu_name,
            "vram_gb":       round(vram_gb, 1) if vram_gb > 0 else None,
            "cpu_cores":     _detect_cpu_cores(),
            "models_loaded": existing_stub.get("models_loaded", []),
            "hns_opt_in":    hns_opt_in if hns_opt_in is not None else existing_stub.get("hns_opt_in"),
            "hns_quota_gb":  hns_quota_gb if hns_quota_gb is not None else existing_stub.get("hns_quota_gb"),
        },
    })


def node_list(store: WillowStore) -> list[dict]:
    """Return all known nodes."""
    return store.list(_NODES_COL)


def alert_pending(store: WillowStore) -> dict | None:
    """Return the most recent pending alert, or None."""
    alerts = store.list(_ALERTS_COL)
    if not alerts:
        return None
    return sorted(alerts, key=lambda a: a.get("created_at", ""), reverse=True)[0]


def alert_dismiss(store: WillowStore, alert_id: str) -> None:
    """Mark an alert as dismissed."""
    alert = store.get(_ALERTS_COL, alert_id)
    if alert:
        alert["dismissed"] = True
        store.put(_ALERTS_COL, alert)
