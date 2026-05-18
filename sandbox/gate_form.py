"""§4 New-feature gate — structured answers before shipping automation. b17: GSSM4 · ΔΣ=42"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NewFeatureGate:
    """Answers required by docs/superpowers/specs/2026-05-12-willow-git-shaped-state-machine.md §4."""

    state_touch: str  # which state 0–7 this moves
    open_pr_equivalent: str
    merge_equivalent: str
    archive_equivalent: str

    def validate(self) -> list[str]:
        errs: list[str] = []
        for field_name, val in (
            ("state_touch", self.state_touch),
            ("open_pr_equivalent", self.open_pr_equivalent),
            ("merge_equivalent", self.merge_equivalent),
            ("archive_equivalent", self.archive_equivalent),
        ):
            if not (val or "").strip():
                errs.append(f"{field_name} is empty")
        return errs

    def ok(self) -> bool:
        return len(self.validate()) == 0
