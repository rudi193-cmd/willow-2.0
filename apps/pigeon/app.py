"""
app.py — Willow Pigeon: unified mailbox TUI.
b17: 1284BC7D  ΔΣ=42

Three-column layout:
  Left:   Perch list (Gmail / Grove channels / OpenClaw sessions)
  Middle: Thread list for the selected perch
  Right:  Message body + compose

Launch standalone:
  python3 -m apps.pigeon

Launch from Grove card:
  subprocess / tmux pane -> python3 -m apps.pigeon
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from apps.pigeon.widgets.perch_list import PerchList
from apps.pigeon.widgets.thread_list import ThreadList
from apps.pigeon.widgets.message_pane import MessagePane
from apps.pigeon.messages import PerchSelected, ThreadSelected


class PigeonApp(App[None]):
    TITLE = "Pigeon"
    CSS_PATH = "pigeon.tcss"

    BINDINGS = [
        Binding("q",         "quit",    "Quit",    show=True),
        Binding("n",         "compose", "New",     show=True),
        Binding("r",         "reply",   "Reply",   show=True),
        Binding("ctrl+r",    "refresh", "Refresh", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="coop"):
            yield PerchList(id="perch-list")
            yield ThreadList(id="thread-list")
            yield MessagePane(id="message-pane")
        yield Footer()

    def on_perch_selected(self, message: PerchSelected) -> None:
        self.query_one(ThreadList).load_perch(message.perch)

    def on_thread_selected(self, message: ThreadSelected) -> None:
        self.query_one(MessagePane).load_thread(message.thread_id, message.backend)

    def action_compose(self) -> None:
        self.query_one(MessagePane).open_compose()

    def action_reply(self) -> None:
        self.query_one(MessagePane).open_reply()

    def action_refresh(self) -> None:
        self.query_one(ThreadList).refresh_threads()


if __name__ == "__main__":
    PigeonApp().run()
