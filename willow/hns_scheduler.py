# willow/hns_scheduler.py — HNS Layer 2: node selection for inference routing. ΔΣ=42
from __future__ import annotations

from core.store_port import StorePort
from willow.grove_coordination import node_list

# Approximate VRAM (GB) per model family. Used when a node has no explicit quota.
_VRAM_TABLE: dict[str, float] = {
    "llama3.3:70b":  42.0,
    "llama3.1:70b":  42.0,
    "llama3.1:8b":    5.5,
    "llama3.2:3b":    2.0,
    "llama3.2:1b":    1.0,
    "mistral:7b":     4.5,
    "nomic-embed-text": 0.5,
}

_SIZE_HINTS: list[tuple[str, float]] = [
    ("70b", 42.0),
    ("13b",  8.0),
    ("8b",   5.5),
    ("7b",   4.5),
    ("3b",   2.0),
    ("1b",   1.0),
]

_VRAM_DEFAULT = 4.0


def _estimate_vram_gb(model_name: str) -> float:
    """Estimate VRAM needed for a model by name. Conservative fallback = 4 GB."""
    if model_name in _VRAM_TABLE:
        return _VRAM_TABLE[model_name]
    # strip quantization suffix (e.g. "llama3.1:8b-instruct-q4_K_M" → "llama3.1:8b")
    base = model_name.split("-")[0] if "-" in model_name else model_name
    if base in _VRAM_TABLE:
        return _VRAM_TABLE[base]
    lower = model_name.lower()
    for suffix, gb in _SIZE_HINTS:
        if suffix in lower:
            return gb
    return _VRAM_DEFAULT


def select_node(store: StorePort, model_name: str) -> dict | None:
    """Return the best opted-in node for model_name, or None if none qualify.

    Selection criteria (all must pass):
    - hns_opt_in is True
    - vram_gb >= estimated need
    - hns_quota_gb is None OR estimated need <= hns_quota_gb

    Tie-break: most VRAM headroom first.
    """
    needed = _estimate_vram_gb(model_name)
    candidates: list[tuple[float, dict]] = []

    for node in node_list(store):
        stub = node.get("2.0_stub", {})
        if not stub.get("hns_opt_in"):
            continue
        vram = stub.get("vram_gb") or 0.0
        quota = stub.get("hns_quota_gb")
        if vram < needed:
            continue
        if quota is not None and needed > quota:
            continue
        candidates.append((vram, node))

    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]
