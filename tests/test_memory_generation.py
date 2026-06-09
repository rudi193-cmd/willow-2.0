"""
tests/test_memory_generation.py

Tests for willow.memory.generation — generation-counter fact store.

These tests use a fake MCP call (no Postgres required) to verify the logic
of the generation counter, put_fact, touch, supersede, demote_stale, and
run_reflection_pass without any real backend dependency.
"""
from __future__ import annotations

import pytest

from willow.memory.generation import GenerationStore


# ---------------------------------------------------------------------------
# Fake MCP backend
# ---------------------------------------------------------------------------

class FakeSoil:
    """In-memory SOIL store. Implements store_get, store_put, store_search."""

    def __init__(self):
        # keyed by (collection, id)
        self._store: dict[tuple[str, str], dict] = {}

    def __call__(self, tool: str, params: dict, timeout: int = 6):
        if tool == "store_get":
            return self._get(params)
        elif tool == "store_put":
            return self._put(params)
        elif tool == "store_search":
            return self._search(params)
        raise ValueError(f"Unknown tool: {tool}")

    def _get(self, params):
        key = (params["collection"], params["id"])
        return dict(self._store[key]) if key in self._store else None

    def _put(self, params):
        rec = params["record"]
        key = (params["collection"], rec["id"])
        self._store[key] = dict(rec)
        return rec

    def _search(self, params):
        coll = params["collection"]
        results = [dict(v) for (c, _), v in self._store.items() if c == coll]
        limit = params.get("limit", 100)
        return results[:limit]


def make_store(agent="hanuman") -> tuple[GenerationStore, FakeSoil]:
    soil = FakeSoil()
    gs = GenerationStore(agent=agent, mcp_call=soil, timeout=5)
    return gs, soil


# ---------------------------------------------------------------------------
# Tests: generation counter
# ---------------------------------------------------------------------------

class TestGenerationCounter:
    def test_initial_generation_is_zero(self):
        gs, _ = make_store()
        assert gs.current_generation() == 0

    def test_increment_generation(self):
        gs, _ = make_store()
        gs._increment_generation()
        assert gs.current_generation() == 1
        gs._increment_generation()
        assert gs.current_generation() == 2

    def test_counter_persists_in_soil(self):
        gs, soil = make_store()
        gs._increment_generation()
        # Check raw SOIL record
        rec = soil._get({"collection": "hanuman/memory/gen_counter", "id": "global"})
        assert rec is not None
        assert rec["value"] == 1


# ---------------------------------------------------------------------------
# Tests: put_fact
# ---------------------------------------------------------------------------

class TestPutFact:
    def test_put_basic_fact(self):
        gs, soil = make_store()
        fact_id = gs.put_fact({"id": "f1", "title": "USER likes Postgres", "type": "preference"})
        assert fact_id == "f1"
        stored = soil._get({"collection": "hanuman/memory/facts", "id": "f1"})
        assert stored is not None
        assert stored["generation"] == 0
        assert stored["superseded_by"] is None
        assert stored["superseded_at"] is None
        assert "created_at" in stored
        assert "last_seen_gen" in stored

    def test_put_fact_requires_id(self):
        gs, _ = make_store()
        with pytest.raises(ValueError, match="must have an 'id' field"):
            gs.put_fact({"title": "no id"})

    def test_put_fact_preserves_caller_dict(self):
        gs, _ = make_store()
        original = {"id": "f2", "content": "test"}
        gs.put_fact(original)
        # Caller's dict must not be mutated
        assert set(original.keys()) == {"id", "content"}

    def test_put_fact_defaults_generation_zero(self):
        gs, soil = make_store()
        gs._increment_generation()  # gen=1
        gs.put_fact({"id": "f3", "title": "New after gen bump"})
        stored = soil._get({"collection": "hanuman/memory/facts", "id": "f3"})
        # Explicit generation default is 0 (it's the fact's own generation level)
        assert stored["generation"] == 0
        # last_seen_gen should be current global gen (1)
        assert stored["last_seen_gen"] == 1


# ---------------------------------------------------------------------------
# Tests: touch
# ---------------------------------------------------------------------------

class TestTouch:
    def test_touch_updates_last_seen_gen(self):
        gs, soil = make_store()
        gs.put_fact({"id": "f1", "title": "test"})
        gs._increment_generation()  # global gen=1
        gs.touch("f1")
        stored = soil._get({"collection": "hanuman/memory/facts", "id": "f1"})
        assert stored["last_seen_gen"] == 1

    def test_touch_nonexistent_is_noop(self):
        gs, _ = make_store()
        # Should not raise
        gs.touch("does-not-exist")

    def test_touch_multiple_times(self):
        gs, soil = make_store()
        gs.put_fact({"id": "f1", "title": "test"})
        for _ in range(3):
            gs._increment_generation()
        gs.touch("f1")
        stored = soil._get({"collection": "hanuman/memory/facts", "id": "f1"})
        assert stored["last_seen_gen"] == 3


# ---------------------------------------------------------------------------
# Tests: supersede
# ---------------------------------------------------------------------------

class TestSupersede:
    def test_supersede_tombstones_old_fact(self):
        gs, soil = make_store()
        gs.put_fact({"id": "f1", "title": "old"})
        gs.put_fact({"id": "f2", "title": "new condensed"})
        gs.supersede("f1", "f2")
        stored = soil._get({"collection": "hanuman/memory/facts", "id": "f1"})
        assert stored["superseded_by"] == "f2"
        assert stored["superseded_at"] is not None

    def test_supersede_nonexistent_is_noop(self):
        gs, _ = make_store()
        # Should not raise
        gs.supersede("does-not-exist", "f2")

    def test_supersede_does_not_affect_new_fact(self):
        gs, soil = make_store()
        gs.put_fact({"id": "f1", "title": "old"})
        gs.put_fact({"id": "f2", "title": "new"})
        gs.supersede("f1", "f2")
        f2 = soil._get({"collection": "hanuman/memory/facts", "id": "f2"})
        assert f2["superseded_at"] is None


# ---------------------------------------------------------------------------
# Tests: demote_stale
# ---------------------------------------------------------------------------

class TestDemoteStale:
    def test_demotes_facts_not_seen_recently(self):
        gs, soil = make_store()
        # Put fact at gen 0
        gs.put_fact({"id": "stale", "title": "old fact"})
        # Advance 4 generations without touching it
        for _ in range(4):
            gs._increment_generation()
        demoted = gs.demote_stale(max_unseen_generations=3)
        assert "stale" in demoted
        stored = soil._get({"collection": "hanuman/memory/facts", "id": "stale"})
        assert stored["superseded_by"] == "DEMOTED"
        assert stored["superseded_at"] is not None

    def test_does_not_demote_recently_touched(self):
        gs, _ = make_store()
        gs.put_fact({"id": "fresh", "title": "fresh fact"})
        for _ in range(4):
            gs._increment_generation()
        gs.touch("fresh")  # last_seen_gen = 4
        demoted = gs.demote_stale(max_unseen_generations=3)
        assert "fresh" not in demoted

    def test_does_not_demote_already_tombstoned(self):
        gs, _ = make_store()
        gs.put_fact({"id": "f1", "title": "already dead"})
        gs.put_fact({"id": "f2", "title": "replacement"})
        gs.supersede("f1", "f2")
        for _ in range(5):
            gs._increment_generation()
        demoted = gs.demote_stale(max_unseen_generations=3)
        # f1 is already superseded — should not appear in demoted list again
        assert "f1" not in demoted

    def test_demote_threshold_boundary(self):
        """Fact at exactly max_unseen_generations distance is NOT demoted (> not >=)."""
        gs, _ = make_store()
        gs.put_fact({"id": "boundary", "title": "on the edge"})
        # gen=0 at write, advance exactly 3 (at boundary)
        for _ in range(3):
            gs._increment_generation()
        demoted = gs.demote_stale(max_unseen_generations=3)
        # current=3, last_seen=0, diff=3 which is NOT > 3 so no demotion
        assert "boundary" not in demoted

    def test_demote_one_past_threshold(self):
        gs, _ = make_store()
        gs.put_fact({"id": "over", "title": "one past"})
        for _ in range(4):
            gs._increment_generation()
        demoted = gs.demote_stale(max_unseen_generations=3)
        # current=4, last_seen=0, diff=4 > 3 → demoted
        assert "over" in demoted


# ---------------------------------------------------------------------------
# Tests: run_reflection_pass
# ---------------------------------------------------------------------------

class TestRunReflectionPass:
    def test_full_reflection_pass(self):
        gs, soil = make_store()
        # Write 3 facts
        gs.put_fact({"id": "keep1", "title": "keep 1"})
        gs.put_fact({"id": "keep2", "title": "keep 2"})
        gs.put_fact({"id": "drop1", "title": "to be superseded"})

        result = gs.run_reflection_pass(
            surviving_ids=["keep1", "keep2"],
            superseded_ids=["drop1"],
            max_unseen_generations=3,
        )

        assert result["new_generation"] == 1
        assert result["surviving"] == 2
        assert result["superseded"] == 1

        # drop1 should be tombstoned
        dropped = soil._get({"collection": "hanuman/memory/facts", "id": "drop1"})
        assert dropped["superseded_by"] == "condensed"
        assert dropped["superseded_at"] is not None

    def test_reflection_increments_generation(self):
        gs, _ = make_store()
        gs.put_fact({"id": "f1", "title": "test"})
        assert gs.current_generation() == 0
        gs.run_reflection_pass(surviving_ids=["f1"], superseded_ids=[])
        assert gs.current_generation() == 1


# ---------------------------------------------------------------------------
# Tests: list_active and stats
# ---------------------------------------------------------------------------

class TestListAndStats:
    def test_list_active_excludes_tombstoned(self):
        gs, _ = make_store()
        gs.put_fact({"id": "live", "title": "live fact"})
        gs.put_fact({"id": "dead", "title": "dead fact"})
        gs.supersede("dead", "live")
        active = gs.list_active()
        ids = [f["id"] for f in active]
        assert "live" in ids
        assert "dead" not in ids

    def test_list_all_includes_tombstoned(self):
        gs, _ = make_store()
        gs.put_fact({"id": "live", "title": "live fact"})
        gs.put_fact({"id": "dead", "title": "dead fact"})
        gs.supersede("dead", "live")
        all_facts = gs.list_all()
        ids = [f["id"] for f in all_facts]
        assert "live" in ids
        assert "dead" in ids

    def test_stats(self):
        gs, _ = make_store()
        gs.put_fact({"id": "f1", "title": "fact 1"})
        gs.put_fact({"id": "f2", "title": "fact 2"})
        gs.put_fact({"id": "f3", "title": "fact 3"})
        gs.supersede("f3", "f1")  # explicit supersede

        # Now demote f2
        for _ in range(4):
            gs._increment_generation()
        gs.touch("f1")  # keep f1 fresh
        gs.demote_stale(max_unseen_generations=3)

        s = gs.stats()
        assert s["current_generation"] == 4
        assert s["total"] == 3
        assert s["active"] == 1  # only f1 (f2 demoted, f3 superseded)
        assert s["tombstoned"] == 2
        assert s["demoted"] == 1
        assert s["superseded"] == 1
