# b17: 1284BC7D  ΔΣ=42
"""
PerchList — left column: mailbox sources (perches).
Backends: gmail, grove, openclaw.
"""
from __future__ import annotations

from textual import work
from textual.containers import VerticalScroll
from textual.widgets import Label, ListItem, ListView

from apps.pigeon.messages import PerchSelected

_STATIC_PERCHES = [
    {"id": "gmail",    "label": "📬 Gmail",         "backend": "gmail"},
    {"id": "grove",    "label": "🌳 Grove Mail",    "backend": "grove"},
    {"id": "openclaw", "label": "🐾 OpenClaw",      "backend": "openclaw"},
]


class PerchList(VerticalScroll):
    def compose(self):
        yield Label("Perches", id="perch-header")
        yield ListView(
            *[ListItem(Label(p["label"]), id=f"perch-{p['id']}") for p in _STATIC_PERCHES],
            id="perch-listview",
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        key     = item_id.removeprefix("perch-")
        perch   = next((p for p in _STATIC_PERCHES if p["id"] == key), None)
        if perch:
            self.post_message(PerchSelected(perch))
