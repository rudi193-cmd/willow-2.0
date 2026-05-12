"""
Git-shaped sandbox — reference implementation of WLGSM policy.
b17: GSSBX · ΔΣ=42
"""
from .engine import GitShapedError, advance, preview_advance
from .gate_form import NewFeatureGate
from .model import (
    ChangeRecord,
    ShapeState,
    allowed_targets,
    create_issue,
    is_terminal,
    new_change_id,
)
from .reporting import allowed_line, json_lines, markdown_table
from .store import JsonStore

__all__ = [
    "GitShapedError",
    "advance",
    "preview_advance",
    "NewFeatureGate",
    "ChangeRecord",
    "ShapeState",
    "allowed_targets",
    "allowed_line",
    "create_issue",
    "is_terminal",
    "new_change_id",
    "JsonStore",
    "markdown_table",
    "json_lines",
]
