# b17: 1284BC7D  ΔΣ=42
"""
MessagePane — right column: message body + compose area.
"""
from __future__ import annotations

from textual import work
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Label, RichLog, TextArea


class MessagePane(Vertical):
    def compose(self):
        yield Label("Message", id="message-header")
        yield RichLog(id="message-body", wrap=True, markup=True)
        yield TextArea(id="compose-area")
        yield Label("n: new  r: reply  ctrl+s: send", id="compose-hint")

    def load_thread(self, thread_id: str, backend: str) -> None:
        self._fetch(thread_id, backend)

    @work(thread=True)
    def _fetch(self, thread_id: str, backend: str) -> None:
        from apps.pigeon.backends import get_backend
        body = get_backend(backend).get_thread(thread_id)
        self.app.call_from_thread(self._render, body)

    def _render(self, body: str) -> None:
        log = self.query_one(RichLog)
        log.clear()
        log.write(body)

    def open_compose(self) -> None:
        self.query_one(TextArea).focus()

    def open_reply(self) -> None:
        self.query_one(TextArea).focus()
