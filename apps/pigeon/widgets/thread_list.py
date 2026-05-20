# b17: 1284BC7D  ΔΣ=42
"""
ThreadList — middle column: threads for the selected perch.
Loads from the appropriate backend stub.
"""
from __future__ import annotations

from textual import work
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Label

from apps.pigeon.messages import ThreadSelected


class ThreadList(VerticalScroll):
    _backend: str = ""

    def compose(self):
        yield Label("Threads", id="thread-header")
        yield DataTable(id="thread-table", cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("From", "Subject", "Date")

    def load_perch(self, perch: dict) -> None:
        self._backend = perch["backend"]
        self.refresh_threads()

    def refresh_threads(self) -> None:
        if self._backend:
            self._fetch(self._backend)

    @work(thread=True)
    def _fetch(self, backend: str) -> None:
        from apps.pigeon.backends import get_backend
        threads = get_backend(backend).list_threads()
        self.app.call_from_thread(self._populate, threads)

    def _populate(self, threads: list[dict]) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for t in threads:
            table.add_row(
                t.get("from", ""),
                t.get("subject", "(no subject)"),
                t.get("date", ""),
                key=t.get("id", ""),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value:
            self.post_message(ThreadSelected(event.row_key.value, self._backend))
