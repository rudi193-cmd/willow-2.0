"""grove/shell.py — Grove OS shell: curses init, event loop, tab management.
b17: WDASH  ΔΣ=42
"""
import curses
import threading
import time
from datetime import datetime

from grove import theme
from grove.mouse import HitMap, HitRegion
from grove.layouts.tabs import TabBar, TabsLayout
from grove.apps.base import App

POLL_INTERVAL = 1.0
MIN_COLS = 80
MIN_ROWS = 24


class Shell:
    def __init__(self, apps: list[App], vitals_app: App = None):
        self._apps = apps
        self._vitals = vitals_app
        self._tab_labels = [a.label for a in apps]
        self._active_idx = 0
        self._hitmap = HitMap()
        self._running = False

    @property
    def active_app(self) -> App:
        return self._apps[self._active_idx]

    def _set_tab(self, idx: int) -> None:
        if 0 <= idx < len(self._apps):
            self.active_app.blur()
            self._active_idx = idx
            self.active_app.focus()

    def run(self, stdscr) -> None:
        self._running = True
        curses.curs_set(0)
        stdscr.keypad(True)
        stdscr.timeout(100)
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        theme.init_pairs()
        stdscr.bkgd(" ", theme.pair("primary"))

        self._apps[0].focus()
        self._tick_all()

        tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        tick_thread.start()

        self._layout_and_render(stdscr)

        while self._running:
            key = stdscr.getch()
            rows, cols = stdscr.getmaxyx()

            if rows < MIN_ROWS or cols < MIN_COLS:
                stdscr.erase()
                msg = f"terminal too small — resize to {MIN_COLS}×{MIN_ROWS} or larger"
                theme.safe_addstr(stdscr, rows // 2,
                                  max(0, (cols - len(msg)) // 2),
                                  msg, theme.pair("degraded"))
                stdscr.refresh()
                if key in (ord("q"), ord("Q")):
                    break
                continue

            if key == curses.KEY_RESIZE:
                self._layout_and_render(stdscr)
                continue

            if key in (ord("q"), ord("Q")):
                self._running = False
                break

            if ord("1") <= key <= ord("9"):
                self._set_tab(key - ord("1"))
                self._layout_and_render(stdscr)
                continue

            if key == ord("\t"):
                self._set_tab((self._active_idx + 1) % len(self._apps))
                self._layout_and_render(stdscr)
                continue

            if key == curses.KEY_MOUSE:
                try:
                    _, mx, my, _, bstate = curses.getmouse()
                    app_id = self._hitmap.resolve(my, mx)
                    if app_id == "tabbar":
                        x = 10
                        for i, label in enumerate(self._tab_labels):
                            text = f"[{label}]" if i == self._active_idx else f" {label} "
                            if x <= mx < x + len(text):
                                self._set_tab(i)
                                break
                            x += len(text) + 1
                    elif app_id and app_id == self.active_app.id:
                        ly, lx = self._hitmap.local_coords(my, mx)
                        self.active_app.handle_mouse(ly, lx, int(bstate))
                    self._layout_and_render(stdscr)
                except curses.error:
                    pass
                continue

            if key != -1:
                if self.active_app.handle_key(key):
                    self._layout_and_render(stdscr)

    def _tick_all(self) -> None:
        for app in (self._apps + ([self._vitals] if self._vitals else [])):
            try:
                app.tick()
            except Exception:
                pass

    def _tick_loop(self) -> None:
        while self._running:
            time.sleep(POLL_INTERVAL)
            self._tick_all()

    def _layout_and_render(self, stdscr) -> None:
        rows, cols = stdscr.getmaxyx()
        layout = TabsLayout(self._tab_labels, rows, cols)
        regions = layout.compute_regions()
        self._hitmap.clear()

        for r in regions:
            try:
                win = stdscr.derwin(r["h"], r["w"], r["row"], r["col"])
            except curses.error:
                continue
            if r["id"] == "tabbar":
                self._hitmap.register(
                    HitRegion(r["row"], r["col"], r["h"], r["w"], "tabbar"))
                ts = datetime.now().strftime("%H:%M:%S")
                TabBar(self._tab_labels).render(win, self._active_idx, ts)
            elif r["id"] == "content":
                self.active_app.attach(win)
                self._hitmap.register(
                    HitRegion(r["row"], r["col"], r["h"], r["w"],
                              self.active_app.id))
                self.active_app.render()
            elif r["id"] == "status":
                self._hitmap.register(
                    HitRegion(r["row"], r["col"], r["h"], r["w"], "status"))
                self._render_status(win)

        curses.doupdate()

    def _render_status(self, win) -> None:
        if win is None:
            return
        _, w = win.getmaxyx()
        win.erase()
        win.bkgd(" ", theme.pair("border"))
        line = self._vitals.line() if self._vitals and hasattr(self._vitals, "line") else " Grove OS"
        theme.safe_addstr(win, 0, 0, theme.truncate(line, w - 1), theme.pair("secondary"))
        win.noutrefresh()
