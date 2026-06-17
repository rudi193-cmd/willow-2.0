"""corpus/tool_denials capture — record blocked tool calls as preference signals.

Verifies:
- upsert_tool_denial() deduplicates by tool_name + reason (not just reason)
- Same tool + same reason → single record with hit counter
- Different tool or different reason → separate records
- Record fields are correct
"""
import pytest
from willow.fylgja.tool_denials import COLLECTION, tool_denial_record_id, upsert_tool_denial


class FakeStore:
    def __init__(self):
        self.data: dict[tuple[str, str], dict] = {}

    def get(self, collection, record_id):
        return self.data.get((collection, record_id))

    def put(self, collection, record, record_id=None):
        self.data[(collection, record_id or record["id"])] = dict(record)

    def all(self, collection):
        return [r for (c, _), r in self.data.items() if c == collection]


def test_same_tool_same_reason_deduplicates():
    store = FakeStore()
    for n in range(4):
        rid = upsert_tool_denial(
            store, tool_name="Bash", reason="Use MCP instead of shell.", session_id=f"s{n}"
        )
    rows = store.all(COLLECTION)
    assert len(rows) == 1
    assert rows[0]["count"] == 4
    assert rows[0]["session_id"] == "s3"
    assert rows[0]["last_seen"] >= rows[0]["created_at"]


def test_different_tools_get_separate_records():
    store = FakeStore()
    upsert_tool_denial(store, tool_name="Bash", reason="Use MCP.", session_id="s")
    upsert_tool_denial(store, tool_name="Write", reason="Use MCP.", session_id="s")
    assert len(store.all(COLLECTION)) == 2


def test_different_reasons_get_separate_records():
    store = FakeStore()
    upsert_tool_denial(store, tool_name="Bash", reason="Use MCP instead of shell.", session_id="s")
    upsert_tool_denial(store, tool_name="Bash", reason="F5 canon guard: prose tool blocked.", session_id="s")
    assert len(store.all(COLLECTION)) == 2


def test_record_id_is_deterministic():
    a = tool_denial_record_id("Bash", "Use MCP.")
    assert a == tool_denial_record_id("Bash", "Use MCP.")
    assert a != tool_denial_record_id("Write", "Use MCP.")
    assert a != tool_denial_record_id("Bash", "F5 canon.")
    assert a.startswith("deny-")


def test_record_fields():
    store = FakeStore()
    upsert_tool_denial(store, tool_name="Bash", reason="Use MCP.", session_id="s1")
    rows = store.all(COLLECTION)
    assert len(rows) == 1
    r = rows[0]
    assert r["type"] == "tool_denial"
    assert r["valence"] == "negative"
    assert r["source"] == "pre_tool_hook"
    assert r["tool_name"] == "Bash"
    assert r["reason"] == "Use MCP."
    assert r["sandbox"] is True
    assert r["b17"] == "CRPS0"
    assert r["count"] == 1
    assert "Bash" in r["content"]
