"""grove/apps/chat.py — Grove channel chat app.
b17: WDASH  ΔΣ=42
"""
import curses
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import grove_db
import soil
import grove_reader
from grove.apps.base import App
from grove import theme

_CHANNEL_ORDER = ["general", "architecture", "handoffs", "readme"]
_SIDEBAR_W = 22


def format_message_header(sender: str, time_str: str) -> str:
    return f"  {sender}  {time_str}"


def advance_cursor(cursors: dict, channel: str, msg_id: int) -> None:
    if msg_id > cursors.get(channel, 0):
        cursors[channel] = msg_id


def _load_cursors() -> dict:
    rec = soil.get("willow-dashboard/channel_cursors", "cursors")
    return dict(rec) if rec else {}


def _save_cursors(cursors: dict) -> None:
    soil.put("willow-dashboard/channel_cursors", "cursors", cursors)


class ChatApp(App):
    id = "chat"
    label = "Chat"

    def __init__(self):
        super().__init__()
        self._channels: list[dict] = []
        self._active_channel: str = ""
        self._messages: list[dict] = []
        self._cursors: dict = {}
        self._input: list[str] = []
        self._scroll: int = 0

    def tick(self) -> None:
        try:
            self._cursors = _load_cursors()
            self._channels = grove_reader.grove_channels(last_seen_ids=self._cursors)
            order = {n: i for i, n in enumerate(_CHANNEL_ORDER)}
            self._channels.sort(key=lambda c: (order.get(c["name"], 99), c["name"]))
            if not self._active_channel and self._channels:
                self._active_channel = self._channels[0]["name"]
            if self._active_channel:
                self._messages = grove_reader.grove_messages(
                    self._active_channel, limit=100)
        except Exception:
            pass

    def _open_channel(self, name: str) -> None:
        if name == self._active_channel:
            return
        self._active_channel = name
        self._scroll = 0
        try:
            self._messages = grove_reader.grove_messages(name, limit=100)
            if self._messages:
                advance_cursor(self._cursors, name, self._messages[-1]["id"])
                _save_cursors(self._cursors)
        except Exception:
            pass

    def render(self) -> None:
        if self._win is None:
            return
        self._win.erase()
        h, w = self._win.getmaxyx()
        border_attr = theme.pair("border")
        sidebar_w = min(_SIDEBAR_W, w // 3)

        # ── Sidebar ───────────────────────────────────────────────────────────
        theme.draw_rounded_box(self._win, 0, 0, h, sidebar_w, border_attr)
        theme.safe_addstr(self._win, 0, 2, " Channels ",
                          theme.pair("accent") | curses.A_BOLD)

        row = 2
        for ch in self._channels:
            if row >= h - 1:
                break
            is_active = ch["name"] == self._active_channel
            unread = ch.get("unread", 0)
            prefix = "▌" if is_active else " "
            name_attr = (theme.pair("accent") | curses.A_BOLD) if is_active else (
                         theme.pair("primary") if unread else theme.pair("secondary"))
            name_str = theme.truncate(f"# {ch['name']}", sidebar_w - 6)
            theme.safe_addstr(self._win, row, 1, prefix,
                              theme.pair("accent") if is_active else 0)
            theme.safe_addstr(self._win, row, 2, name_str, name_attr)
            if unread:
                badge = str(unread)
                badge_x = sidebar_w - len(badge) - 2
                theme.safe_addstr(self._win, row, badge_x, badge,
                                  theme.pair("unread") | curses.A_BOLD)
            row += 1

        # ── Main pane ─────────────────────────────────────────────────────────
        main_x = sidebar_w + 1
        main_w = w - main_x
        if main_w < 10:
            self._win.noutrefresh()
            return

        theme.draw_rounded_box(self._win, 0, main_x, h, main_w, border_attr)
        ch_title = f" # {self._active_channel} " if self._active_channel else " Chat "
        theme.safe_addstr(self._win, 0, main_x + 2, ch_title,
                          theme.pair("primary") | curses.A_BOLD)

        visible_rows = h - 5
        msg_lines = []
        for msg in self._messages:
            ts = ""
            ca = msg.get("created_at")
            if ca:
                try:
                    ts = ca.strftime("%H:%M")
                except Exception:
                    ts = str(ca)[-8:-3]
            msg_lines.append((msg.get("sender", "?"), ts, msg.get("content", "")))

        start = max(0, len(msg_lines) - visible_rows - self._scroll)
        visible = msg_lines[start: start + visible_rows]

        msg_row = 1
        for sender, ts, content in visible:
            if msg_row >= h - 3:
                break
            sender_pair = curses.color_pair(theme.agent_pair(sender))
            theme.safe_addstr(self._win, msg_row, main_x + 2,
                              f"  {sender}", sender_pair | curses.A_BOLD)
            theme.safe_addstr(self._win, msg_row,
                              main_x + 4 + len(sender),
                              ts, theme.pair("secondary"))
            msg_row += 1
            body_w = max(10, main_w - 7)
            for i in range(0, max(1, len(content)), body_w):
                if msg_row >= h - 3:
                    break
                theme.safe_addstr(self._win, msg_row, main_x + 4,
                                  content[i:i + body_w], theme.pair("primary"))
                msg_row += 1

        # Input bar
        input_y = h - 2
        input_inner_w = max(4, main_w - 4)
        input_str = "".join(self._input)
        placeholder = (f"Message #{self._active_channel}..."
                       if self._active_channel else "Select a channel")
        display = input_str if input_str else placeholder
        input_attr = theme.pair("input") if input_str else theme.pair("secondary")
        theme.safe_addstr(self._win, input_y - 1, main_x + 1,
                          "─" * (main_w - 2), theme.pair("border"))
        theme.safe_addstr(self._win, input_y, main_x + 2,
                          theme.truncate(display, input_inner_w), input_attr)

        self._win.noutrefresh()

    def handle_key(self, key: int) -> bool:
        if key == curses.KEY_UP:
            self._scroll += 1
            return True
        if key == curses.KEY_DOWN:
            self._scroll = max(0, self._scroll - 1)
            return True
        if key in (curses.KEY_BACKSPACE, 127):
            if self._input:
                self._input.pop()
            return True
        if key in (curses.KEY_ENTER, 10, 13):
            msg = "".join(self._input).strip()
            if msg and self._active_channel:
                self._send(msg)
            return True
        if 32 <= key <= 126:
            self._input.append(chr(key))
            return True
        return False

    def handle_mouse(self, y: int, x: int, btn: int) -> bool:
        sidebar_w = min(_SIDEBAR_W, self.size()[1] // 3)
        if x < sidebar_w and 2 <= y < 2 + len(self._channels):
            self._open_channel(self._channels[y - 2]["name"])
            return True
        return False

    def _send(self, text: str) -> None:
        conn = None
        try:
            conn = grove_db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id FROM grove.channels WHERE name = %s LIMIT 1",
                        (self._active_channel,))
            row = cur.fetchone()
            if row:
                agent = os.environ.get("WILLOW_AGENT_NAME", "hanuman")
                cur.execute(
                    "INSERT INTO grove.messages (channel_id, sender, content)"
                    " VALUES (%s, %s, %s)",
                    (row[0], agent, text),
                )
                conn.commit()
        except Exception:
            pass
        finally:
            if conn is not None:
                grove_db.release_connection(conn)
        self._input.clear()
        try:
            self._messages = grove_reader.grove_messages(
                self._active_channel, limit=100)
        except Exception:
            pass
