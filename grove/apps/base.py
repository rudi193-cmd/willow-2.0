"""grove/apps/base.py — App abstract base class.
b17: WDASH  ΔΣ=42
"""
from abc import ABC, abstractmethod


class App(ABC):
    """Base class for all Grove apps."""
    id: str = ""
    label: str = ""

    def __init__(self) -> None:
        self._win = None
        self._focused: bool = False

    def attach(self, win) -> None:
        self._win = win

    def focus(self) -> None:
        self._focused = True

    def blur(self) -> None:
        self._focused = False

    @property
    def win(self):
        return self._win

    @property
    def focused(self) -> bool:
        return self._focused

    def size(self) -> tuple[int, int]:
        if self._win is None:
            return (0, 0)
        return self._win.getmaxyx()

    @abstractmethod
    def render(self) -> None:
        """Draw the app into self._win. Must not raise."""

    def handle_key(self, key: int) -> bool:
        return False

    def handle_mouse(self, y: int, x: int, btn: int) -> bool:
        return False

    def tick(self) -> None:
        pass
