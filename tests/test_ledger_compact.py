"""compact_ledger_entry — oversized ledger content must not replay at read time.

Regression: the 2026-06-12 bitemporal_repair entry carried a 174-record
before-state in content; ledger_read(limit=3) injected it into every boot.
"""
import json

from core.pg_bridge import PgBridge


def _entry(content):
    return {
        "id": "test-id",
        "project": "willow",
        "event_type": "check_in",
        "content": content,
        "prev_hash": "p",
        "hash": "h",
    }


def test_small_content_passes_through_unchanged():
    entry = _entry({"summary": "small", "tags": ["a"]})
    out = PgBridge.compact_ledger_entry(entry, max_chars=2000)
    assert out == entry


def test_oversized_content_is_compacted():
    bulk = {
        "summary": "Repairing 174 violations",
        "a_count": 165,
        "before": {"A": [{"id": f"X{i}", "old": None} for i in range(200)]},
    }
    entry = _entry(bulk)
    assert len(json.dumps(bulk)) > 2000
    out = PgBridge.compact_ledger_entry(entry, max_chars=2000)
    content = out["content"]
    assert content["_truncated"] is True
    assert content["summary"] == "Repairing 174 violations"
    assert content["a_count"] == 165
    assert "before" not in content
    assert sorted(content["_keys"]) == ["a_count", "before", "summary"]
    assert "test-id" in content["_note"]
    assert len(json.dumps(content)) < len(json.dumps(bulk))


def test_original_entry_not_mutated():
    bulk = _entry({"big": ["x" * 100] * 100})
    snapshot = json.dumps(bulk, sort_keys=True)
    PgBridge.compact_ledger_entry(bulk, max_chars=2000)
    assert json.dumps(bulk, sort_keys=True) == snapshot


def test_non_dict_content_compacts_without_keys():
    entry = _entry("y" * 5000)
    out = PgBridge.compact_ledger_entry(entry, max_chars=2000)
    assert out["content"]["_truncated"] is True
    assert "_keys" not in out["content"]
