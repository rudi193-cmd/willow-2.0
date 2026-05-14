"""grove/mouse.py — Hit region registry for mouse click routing.
b17: WDASH  ΔΣ=42
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class HitRegion:
    y: int
    x: int
    h: int
    w: int
    app_id: str


class HitMap:
    """Stores rectangular hit regions and resolves (y, x) clicks to app ids."""

    def __init__(self):
        self._regions: list[HitRegion] = []

    def register(self, region: HitRegion) -> None:
        self._regions.append(region)

    def clear(self) -> None:
        self._regions.clear()

    def resolve(self, y: int, x: int) -> Optional[str]:
        result = None
        for r in self._regions:
            if r.y <= y < r.y + r.h and r.x <= x < r.x + r.w:
                result = r.app_id
        return result

    def local_coords(self, y: int, x: int) -> tuple[int, int]:
        for r in reversed(self._regions):
            if r.y <= y < r.y + r.h and r.x <= x < r.x + r.w:
                return (y - r.y, x - r.x)
        return (y, x)
