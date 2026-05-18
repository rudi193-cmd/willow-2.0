"""grove/theme.py — 256-color palette, borders, draw helpers.
b17: WDASH  ΔΣ=42
"""
import curses
import hashlib

_C = {
    "bg":        235,
    "border":    238,
    "secondary": 245,
    "primary":   253,
    "accent":    99,
    "unread":    220,
    "online":    77,
    "idle":      243,
    "busy":      214,
    "healthy":   77,
    "degraded":  214,
    "down":      203,
    "input_bg":  236,
}

_AGENT_PALETTE = [87, 213, 227, 120, 111, 209, 51]

_PAIR = {
    "primary":   20,
    "secondary": 21,
    "accent":    22,
    "unread":    23,
    "online":    24,
    "idle":      25,
    "busy":      26,
    "healthy":   27,
    "degraded":  28,
    "down":      29,
    "border":    30,
    "input":     31,
}
_AGENT_PAIR_BASE = 40

BORDERS = {"tl": "╭", "tr": "╮", "bl": "╰", "br": "╯", "h": "─", "v": "│"}

STATUS_GLYPHS = {"online": "●", "idle": "○", "busy": "◐", "unknown": "·"}


def status_glyph(state: str) -> str:
    return STATUS_GLYPHS.get(state, "·")


def _agent_idx(name: str) -> int:
    return int(hashlib.md5(name.encode()).hexdigest(), 16) % len(_AGENT_PALETTE)


def agent_color_index(name: str) -> int:
    return _AGENT_PALETTE[_agent_idx(name)]


def agent_pair(name: str) -> int:
    return _AGENT_PAIR_BASE + _agent_idx(name)


def truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 5:
        return text[:width]
    return text[:width - 3] + "..."


def init_pairs() -> None:
    if not curses.has_colors():
        return
    curses.start_color()
    curses.use_default_colors()
    use256 = curses.COLORS >= 256

    def _pair(idx: str, fg_key: str):
        fg = _C[fg_key] if use256 else curses.COLOR_WHITE
        curses.init_pair(_PAIR[idx], fg, -1)

    _pair("primary",   "primary")
    _pair("secondary", "secondary")
    _pair("accent",    "accent")
    _pair("unread",    "unread")
    _pair("online",    "online")
    _pair("idle",      "idle")
    _pair("busy",      "busy")
    _pair("healthy",   "healthy")
    _pair("degraded",  "degraded")
    _pair("down",      "down")
    _pair("border",    "border")
    curses.init_pair(_PAIR["input"], _C["primary"] if use256 else curses.COLOR_WHITE,
                     _C["input_bg"] if use256 else -1)

    for i, color in enumerate(_AGENT_PALETTE):
        c = color if use256 else [curses.COLOR_CYAN, curses.COLOR_MAGENTA,
            curses.COLOR_YELLOW, curses.COLOR_GREEN, curses.COLOR_BLUE,
            curses.COLOR_RED, curses.COLOR_CYAN][i]
        curses.init_pair(_AGENT_PAIR_BASE + i, c, -1)


def pair(name: str) -> int:
    return curses.color_pair(_PAIR.get(name, 0))


def safe_addstr(win, y: int, x: int, text: str, attr: int = 0) -> None:
    if win is None:
        return
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w:
        return
    clipped = text[:max(0, w - x)]
    if not clipped:
        return
    try:
        win.addstr(y, x, clipped, attr)
    except curses.error:
        pass


def draw_rounded_box(win, y: int, x: int, h: int, w: int, attr: int = 0) -> None:
    safe_addstr(win, y,         x,         BORDERS["tl"] + BORDERS["h"] * (w - 2) + BORDERS["tr"], attr)
    safe_addstr(win, y + h - 1, x,         BORDERS["bl"] + BORDERS["h"] * (w - 2) + BORDERS["br"], attr)
    for row in range(1, h - 1):
        safe_addstr(win, y + row, x,         BORDERS["v"], attr)
        safe_addstr(win, y + row, x + w - 1, BORDERS["v"], attr)
