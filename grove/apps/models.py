"""grove/apps/models.py — Local + API model switcher app.
b17: WDASH  ΔΣ=42
"""
import curses
import json
import urllib.request
import urllib.error
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import soil
from grove.apps.base import App
from grove import theme


def list_models() -> list[str]:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            data = json.loads(r.read())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def get_active_model() -> str:
    rec = soil.get("willow-dashboard/config", "active_model")
    return rec.get("value", "") if rec else ""


def set_active_model(name: str) -> None:
    soil.put("willow-dashboard/config", "active_model", {"value": name})


class ModelsApp(App):
    id = "models"
    label = "Models"

    def __init__(self):
        super().__init__()
        self._models: list[str] = []
        self._active: str = ""
        self._cursor: int = 0

    def tick(self) -> None:
        self._models = list_models()
        self._active = get_active_model()
        if not self._active and self._models:
            ygg = [m for m in self._models if "yggdrasil" in m]
            self._active = ygg[0] if ygg else self._models[0]

    def _local_models(self) -> list[str]:
        return [m for m in self._models if "nomic" not in m.lower()]

    def render(self) -> None:
        if self._win is None:
            return
        self._win.erase()
        h, w = self._win.getmaxyx()
        border_attr = theme.pair("border")

        theme.draw_rounded_box(self._win, 0, 0, h, w, border_attr)
        theme.safe_addstr(self._win, 0, 2, " Models ", theme.pair("accent") | curses.A_BOLD)

        if not self._models:
            theme.safe_addstr(self._win, 2, 2, "Ollama unreachable", theme.pair("secondary"))
            self._win.noutrefresh()
            return

        local = self._local_models()
        row = 2
        theme.safe_addstr(self._win, row, 2, "Local (Ollama)", theme.pair("secondary"))
        row += 1

        for i, name in enumerate(local):
            if row >= h - 1:
                break
            is_active = name == self._active
            is_cursor = i == self._cursor and self._focused
            prefix = "▌ " if is_active else "  "
            attr = (theme.pair("accent") | curses.A_BOLD) if is_active else (
                   curses.A_REVERSE if is_cursor else theme.pair("primary"))
            short = theme.truncate(name, w - 6)
            theme.safe_addstr(self._win, row, 2, prefix + short, attr)
            row += 1

        if self._focused:
            theme.safe_addstr(self._win, h - 2, 2,
                              "↑↓ move  Enter switch", theme.pair("secondary"))

        self._win.noutrefresh()

    def handle_key(self, key: int) -> bool:
        local = self._local_models()
        if key == curses.KEY_UP:
            self._cursor = max(0, self._cursor - 1)
            return True
        if key == curses.KEY_DOWN:
            self._cursor = min(len(local) - 1, self._cursor + 1)
            return True
        if key in (curses.KEY_ENTER, 10, 13):
            if 0 <= self._cursor < len(local):
                set_active_model(local[self._cursor])
                self._active = local[self._cursor]
            return True
        return False
