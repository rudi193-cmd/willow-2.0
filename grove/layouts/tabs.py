"""grove/layouts/tabs.py — Tab bar layout: top bar + content pane + status strip.
b17: WDASH  ΔΣ=42
"""
import curses
from grove import theme


class TabBar:
    def __init__(self, labels: list[str]):
        self._labels = labels

    def render_text(self, active: int, width: int) -> str:
        parts = []
        for i, label in enumerate(self._labels):
            parts.append(f"[{label}]" if i == active else f" {label} ")
        return "  " + "  ".join(parts)

    def render(self, win, active: int, time_str: str = "") -> None:
        if win is None:
            return
        h, w = win.getmaxyx()
        win.erase()
        win.bkgd(" ", theme.pair("border"))

        theme.safe_addstr(win, 0, 1, "⬡ Grove", theme.pair("accent") | curses.A_BOLD)
        x = 10
        for i, label in enumerate(self._labels):
            if x >= w - 20:
                break
            if i == active:
                attr = theme.pair("primary") | curses.A_BOLD | curses.A_REVERSE
                text = f"[{label}]"
            else:
                attr = theme.pair("secondary")
                text = f" {label} "
            theme.safe_addstr(win, 0, x, text, attr)
            x += len(text) + 1

        if time_str:
            ts_x = max(x + 2, w - len(time_str) - 2)
            theme.safe_addstr(win, 0, ts_x, time_str, theme.pair("secondary"))

        win.noutrefresh()


class TabsLayout:
    TAB_BAR_H = 1
    STATUS_H  = 1

    def __init__(self, tab_labels: list[str], rows: int, cols: int):
        self._labels = tab_labels
        self._rows = rows
        self._cols = cols

    def compute_regions(self) -> list[dict]:
        content_h = max(1, self._rows - self.TAB_BAR_H - self.STATUS_H)
        return [
            {"id": "tabbar",  "row": 0,                    "col": 0,
             "h": self.TAB_BAR_H, "w": self._cols},
            {"id": "content", "row": self.TAB_BAR_H,        "col": 0,
             "h": content_h,      "w": self._cols},
            {"id": "status",  "row": self._rows - self.STATUS_H, "col": 0,
             "h": self.STATUS_H,  "w": self._cols},
        ]
