"""
Git-shaped change lifecycle — reference types for sandbox / fleet alignment.
b17: GSSM0 · ΔΣ=42
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ShapeState(str, Enum):
    """Maps to policy doc §2 rows 0–7 (names shortened for JSON)."""

    issue = "issue"  # 0
    draft = "draft"  # 1 Draft PR
    open = "open"  # 2 Open PR
    checks = "checks"  # 3
    review = "review"  # 4
    merged = "merged"  # 5
    release = "release"  # 6 optional
    archived = "archived"  # 7


# Forward + repair arcs (git-shaped: request changes, fix CI)
_ALLOWED: dict[ShapeState, frozenset[ShapeState]] = {
    ShapeState.issue: frozenset({ShapeState.draft}),
    ShapeState.draft: frozenset({ShapeState.open}),
    ShapeState.open: frozenset({ShapeState.checks}),
    ShapeState.checks: frozenset({ShapeState.review, ShapeState.open}),  # open = fix needed
    ShapeState.review: frozenset({ShapeState.merged, ShapeState.open}),  # open = changes requested
    ShapeState.merged: frozenset({ShapeState.release, ShapeState.archived}),
    ShapeState.release: frozenset({ShapeState.archived}),
    ShapeState.archived: frozenset(),
}


def allowed_targets(state: ShapeState) -> frozenset[ShapeState]:
    return _ALLOWED.get(state, frozenset())


def is_terminal(state: ShapeState) -> bool:
    return state == ShapeState.archived


@dataclass
class Transition:
    at: str
    from_state: ShapeState
    to_state: ShapeState
    actor: str
    note: str = ""


def new_change_id() -> str:
    return f"gs-{uuid.uuid4().hex[:12]}"


@dataclass
class ChangeRecord:
    """One bounded unit of work (the 'PR object' in policy §3)."""

    id: str
    title: str
    state: ShapeState
    created_at: str = ""
    updated_at: str = ""
    subject: str = ""
    grove_channel: str = ""
    kb_seed_hint: str = ""
    fork_id: str = ""
    flag_id: str = ""
    history: list[Transition] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        d["history"] = [
            {
                "at": h.at,
                "from_state": h.from_state.value,
                "to_state": h.to_state.value,
                "actor": h.actor,
                "note": h.note,
            }
            for h in self.history
        ]
        return d

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> ChangeRecord:
        hist = []
        for h in d.get("history") or []:
            hist.append(
                Transition(
                    at=h["at"],
                    from_state=ShapeState(h["from_state"]),
                    to_state=ShapeState(h["to_state"]),
                    actor=h["actor"],
                    note=h.get("note") or "",
                )
            )
        created = d.get("created_at") or ""
        updated = d.get("updated_at") or ""
        if not created and hist:
            created = hist[0].at
        if not updated and hist:
            updated = hist[-1].at
        return cls(
            id=d["id"],
            title=d["title"],
            state=ShapeState(d["state"]),
            created_at=created,
            updated_at=updated,
            subject=d.get("subject") or "",
            grove_channel=d.get("grove_channel") or "",
            kb_seed_hint=d.get("kb_seed_hint") or "",
            fork_id=d.get("fork_id") or "",
            flag_id=d.get("flag_id") or "",
            history=hist,
        )


def create_issue(
    title: str,
    *,
    subject: str = "",
    flag_id: str = "",
    grove_channel: str = "",
    kb_seed_hint: str = "",
    fork_id: str = "",
) -> ChangeRecord:
    """Create a change at state **issue**."""
    now = _utc_now()
    return ChangeRecord(
        id=new_change_id(),
        title=title,
        state=ShapeState.issue,
        created_at=now,
        updated_at=now,
        subject=subject,
        grove_channel=grove_channel,
        kb_seed_hint=kb_seed_hint,
        fork_id=fork_id,
        flag_id=flag_id,
        history=[],
    )
