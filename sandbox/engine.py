"""Transition engine — illegal skips raise GitShapedError. b17: GSSM3 · ΔΣ=42"""
from __future__ import annotations

import copy
from datetime import datetime, timezone

from .model import ChangeRecord, ShapeState, Transition, allowed_targets


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GitShapedError(ValueError):
    pass


def advance(
    change: ChangeRecord,
    to_state: ShapeState,
    *,
    actor: str,
    note: str = "",
) -> ChangeRecord:
    cur = change.state
    if to_state not in allowed_targets(cur):
        allowed = ", ".join(s.value for s in allowed_targets(cur)) or "(none)"
        raise GitShapedError(
            f"Illegal transition {cur.value} → {to_state.value}. "
            f"Allowed from {cur.value}: {allowed}"
        )
    tr = Transition(
        at=_utc_now(),
        from_state=cur,
        to_state=to_state,
        actor=actor,
        note=note,
    )
    change.state = to_state
    change.history.append(tr)
    change.updated_at = tr.at
    return change


def preview_advance(
    change: ChangeRecord,
    to_state: ShapeState,
    *,
    actor: str,
    note: str = "",
) -> ChangeRecord:
    """Return the record **after** a transition without mutating the original."""
    dup = copy.deepcopy(change)
    return advance(dup, to_state, actor=actor, note=note)
