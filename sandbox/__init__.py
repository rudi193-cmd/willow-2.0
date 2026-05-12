"""
Git-shaped sandbox — reference implementation of WLGSM policy.
b17: GSSBX · ΔΣ=42
"""
from .engine import GitShapedError, advance
from .gate_form import NewFeatureGate
from .model import ChangeRecord, ShapeState, allowed_targets, create_issue, is_terminal, new_change_id
from .store import JsonStore

__all__ = [
    "GitShapedError",
    "advance",
    "NewFeatureGate",
    "ChangeRecord",
    "ShapeState",
    "allowed_targets",
    "create_issue",
    "is_terminal",
    "new_change_id",
    "JsonStore",
]
