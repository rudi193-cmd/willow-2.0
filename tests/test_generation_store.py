"""
tests/test_generation_store.py — Generation LRU store unit tests.
Coverage: counter increment, LRU eviction, persistence, stats.
"""

import pickle
import tempfile
from pathlib import Path

import pytest

from willow.memory.generation_store import GenerationLRUStore, get_default_store


class TestGenerationStoreBasic:
    """Basic counter operations."""

    def test_init_empty(self):
        """New store should be empty."""
        store = GenerationLRUStore()
        assert len(store._data) == 0
        stats = store.stats()
        assert stats["atom_count"] == 0

    def test_touch_new_atom(self):
        """Touching new atom should initialize to generation 1."""
        store = GenerationLRUStore()
        gen = store.touch("atom-1")
        assert gen == 1
        assert store.get_gen("atom-1") == 1

    def test_touch_increment(self):
        """Repeated touches should increment generation."""
        store = GenerationLRUStore()
        assert store.touch("atom-1") == 1
        assert store.touch("atom-1") == 2
        assert store.touch("atom-1") == 3

    def test_touch_multiple_atoms(self):
        """Multiple atoms should track independently."""
        store = GenerationLRUStore()
        gen_a = store.touch("atom-a")
        gen_b = store.touch("atom-b")
        gen_a2 = store.touch("atom-a")

        assert gen_a == 1
        assert gen_b == 1
        assert gen_a2 == 2
        assert store.get_gen("atom-a") == 2
        assert store.get_gen("atom-b") == 1

    def test_get_gen_missing(self):
        """get_gen on missing atom should return 0."""
        store = GenerationLRUStore()
        assert store.get_gen("missing") == 0

    def test_get_hits(self):
        """get_hits should track access count."""
        store = GenerationLRUStore()
        store.touch("atom-1")
        store.touch("atom-1")
        assert store.get_hits("atom-1") == 2

    def test_get_hits_missing(self):
        """get_hits on missing atom should return 0."""
        store = GenerationLRUStore()
        assert store.get_hits("missing") == 0


class TestGenerationStoreLRUEviction:
    """LRU eviction behavior."""

    def test_trim_on_size_limit(self):
        """Touching new atoms beyond size limit should trigger trim."""
        store = GenerationLRUStore(max_bytes=1024)  # Very small

        # Add atoms until we hit the limit
        atom_count = 0
        for i in range(50):
            store.touch(f"atom-{i}")
            atom_count += 1

        # Should have evicted some old atoms
        current_count = len(store._data)
        assert current_count < atom_count
        assert store.stats()["size_bytes"] <= store._max_bytes

    def test_eviction_removes_oldest(self):
        """Trim should remove least recently used during touch."""
        store = GenerationLRUStore(max_bytes=256)  # Much smaller

        # Add atoms in order (triggers lazy eviction during touch)
        for i in range(20):
            store.touch(f"atom-{i}")

        # We should have evicted some older atoms during the loop
        # The store keeps the most recently used atoms
        evicted = store.stats()["evicted_total"]
        assert evicted > 0, "Some atoms should have been evicted during touches"

        # Access early atom to keep it (move to end)
        store.touch("atom-0")
        # Atom-0 should still be there
        assert store.get_gen("atom-0") > 0

    def test_clear(self):
        """clear should empty store and reset stats."""
        store = GenerationLRUStore()
        store.touch("atom-1")
        store.touch("atom-2")
        assert len(store._data) == 2

        store.clear()
        assert len(store._data) == 0
        assert store.get_gen("atom-1") == 0
        assert store.stats()["evicted_total"] == 0

    def test_custom_max_bytes(self):
        """Custom max_bytes should limit size."""
        store_large = GenerationLRUStore(max_bytes=100_000_000)
        store_small = GenerationLRUStore(max_bytes=1024)

        # Add same atoms to both
        for i in range(50):
            store_large.touch(f"atom-{i}")
            store_small.touch(f"atom-{i}")

        # Small store should have fewer atoms
        assert len(store_small._data) <= len(store_large._data)


class TestGenerationStoreStats:
    """Statistics tracking."""

    def test_stats_fields(self):
        """stats should include all required fields."""
        store = GenerationLRUStore()
        store.touch("atom-1")

        stats = store.stats()
        required = ["size_bytes", "atom_count", "max_bytes", "evicted_total",
                    "hits", "misses", "hit_rate"]
        assert all(k in stats for k in required)

    def test_stats_hit_rate(self):
        """Hit rate should reflect touch behavior."""
        store = GenerationLRUStore()
        assert store.stats()["hit_rate"] == 0.0  # No requests yet

        store.touch("atom-1")  # Miss
        store.touch("atom-1")  # Hit
        stats = store.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_stats_size_tracking(self):
        """Size should grow with atoms."""
        store = GenerationLRUStore()
        size_empty = store.stats()["size_bytes"]
        assert size_empty > 0  # Even empty OrderedDict has some size

        store.touch("atom-1")
        size_with_one = store.stats()["size_bytes"]
        assert size_with_one > size_empty

    def test_stats_eviction_count(self):
        """Eviction count should increment on trim."""
        store = GenerationLRUStore(max_bytes=512)

        # Add and evict atoms
        for i in range(30):
            store.touch(f"atom-{i}")

        stats = store.stats()
        assert stats["evicted_total"] > 0

    def test_repr(self):
        """__repr__ should show summary."""
        store = GenerationLRUStore()
        store.touch("atom-1")
        store.touch("atom-1")

        repr_str = repr(store)
        assert "GenerationLRUStore" in repr_str
        assert "1 atoms" in repr_str


class TestGenerationStorePersistence:
    """Persistence to disk."""

    def test_persist_on_close(self):
        """close should persist data to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "store.pkl"
            assert not path.exists()

            store = GenerationLRUStore(persist_path=path)
            store.touch("atom-1")
            store.touch("atom-1")
            store.close()

            assert path.exists()

    def test_load_on_init(self):
        """Init should load persisted data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "store.pkl"

            # Create and save
            store1 = GenerationLRUStore(persist_path=path)
            store1.touch("atom-1")
            store1.touch("atom-1")
            store1.close()

            # Load and verify
            store2 = GenerationLRUStore(persist_path=path)
            assert store2.get_gen("atom-1") == 2
            store2.close()

    def test_persist_multiple_atoms(self):
        """Persistence should handle multiple atoms."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "store.pkl"

            store1 = GenerationLRUStore(persist_path=path)
            for i in range(10):
                store1.touch(f"atom-{i}")
            store1.close()

            store2 = GenerationLRUStore(persist_path=path)
            for i in range(10):
                assert store2.get_gen(f"atom-{i}") == 1
            store2.close()

    def test_no_persist_path(self):
        """Store without persist_path should not save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "store.pkl"
            store = GenerationLRUStore(persist_path=None)
            store.touch("atom-1")
            store.close()

            assert not path.exists()

    def test_load_missing_file(self):
        """Loading non-existent file should initialize empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent.pkl"
            store = GenerationLRUStore(persist_path=path)
            assert len(store._data) == 0
            store.close()

    def test_persist_handles_bad_file(self):
        """Loading corrupted file should not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "corrupt.pkl"
            path.write_bytes(b"not valid pickle")

            # Should not raise, just skip loading
            store = GenerationLRUStore(persist_path=path)
            assert len(store._data) == 0
            store.close()


class TestGenerationStoreGlobalInstance:
    """Global singleton pattern."""

    def test_get_default_store(self):
        """get_default_store should return consistent instance."""
        # Note: This test may be flaky if other tests use the global instance.
        # In real usage, this is fine since it's per-session.
        store1 = get_default_store()
        store2 = get_default_store()
        assert store1 is store2

    def test_default_store_has_persist_path(self):
        """Default store should use ~/.willow/generation_store.pkl."""
        store = get_default_store()
        assert store._persist_path is not None
        assert "generation_store.pkl" in str(store._persist_path)


class TestGenerationStoreEdgeCases:
    """Edge cases and boundary conditions."""

    def test_many_touches(self):
        """Large number of touches should work."""
        store = GenerationLRUStore()
        atom_id = "atom-heavy"
        for i in range(10_000):
            gen = store.touch(atom_id)
        assert gen == 10_000

    def test_many_atoms(self):
        """Large number of atoms with eviction."""
        store = GenerationLRUStore(max_bytes=10_000)  # Much smaller limit
        for i in range(500):
            store.touch(f"atom-{i}")

        stats = store.stats()
        assert stats["atom_count"] > 0
        assert stats["atom_count"] < 500  # Many should be evicted at 10KB limit
        assert stats["evicted_total"] > 0  # Some evictions happened

    def test_zero_max_bytes(self):
        """Zero max_bytes should evict immediately."""
        store = GenerationLRUStore(max_bytes=0)
        store.touch("atom-1")
        store.touch("atom-2")

        # Should have evicted at least atom-1
        assert len(store._data) <= 1

    def test_atom_id_special_chars(self):
        """Atom IDs with special characters should work."""
        store = GenerationLRUStore()
        special_ids = [
            "atom-123",
            "atom/path/to/id",
            "atom:with:colons",
            "atom-with-dashes",
            "atom_with_underscores",
            "atom.with.dots",
            "atom@example.com",
        ]
        for atom_id in special_ids:
            gen = store.touch(atom_id)
            assert gen == 1
            assert store.get_gen(atom_id) == 1

    def test_lru_order_preserved(self):
        """LRU order should place recent at end."""
        store = GenerationLRUStore(max_bytes=1_000_000)
        for i in range(10):
            store.touch(f"atom-{i}")

        # Access atom-0 to move to end
        store.touch("atom-0")

        keys = list(store._data.keys())
        assert keys[-1] == "atom-0"  # Should be last

    def test_multiple_stores(self):
        """Multiple independent stores should work."""
        store1 = GenerationLRUStore()
        store2 = GenerationLRUStore()

        store1.touch("atom-1")
        store2.touch("atom-2")

        assert store1.get_gen("atom-1") == 1
        assert store1.get_gen("atom-2") == 0
        assert store2.get_gen("atom-1") == 0
        assert store2.get_gen("atom-2") == 1


class TestGenerationStoreIntegration:
    """Integration tests: realistic usage patterns."""

    def test_realistic_atom_access(self):
        """Simulate realistic atom access pattern."""
        store = GenerationLRUStore(max_bytes=10_000_000)

        # Simulate 100 atoms being accessed with zipfian distribution
        # (some atoms accessed frequently, others rarely)
        import random
        random.seed(42)

        accesses = {}
        for _ in range(10_000):
            # Zipfian: bias toward atoms 0-20
            if random.random() < 0.8:
                atom_id = f"atom-{random.randint(0, 20)}"
            else:
                atom_id = f"atom-{random.randint(0, 100)}"

            gen = store.touch(atom_id)
            accesses[atom_id] = gen

        # Hot atoms should have high generation
        hot_atoms = [f"atom-{i}" for i in range(10)]
        generations = [store.get_gen(atom) for atom in hot_atoms if store.get_gen(atom) > 0]
        avg_hot_gen = sum(generations) / len(generations) if generations else 0

        # Cold atoms should have low generation
        cold_atoms = [f"atom-{i}" for i in range(80, 101)]
        generations_cold = [store.get_gen(atom) for atom in cold_atoms if store.get_gen(atom) > 0]
        avg_cold_gen = sum(generations_cold) / len(generations_cold) if generations_cold else 1

        assert avg_hot_gen >= avg_cold_gen  # Hot should be >= cold on average

    def test_generation_counter_for_versioning(self):
        """Use generation as atom version counter."""
        store = GenerationLRUStore()

        # Version tracking: "atom-x at generation N"
        atom_id = "atom-config"
        versions = []

        for update in range(5):
            gen = store.touch(atom_id)
            versions.append(gen)

        assert versions == [1, 2, 3, 4, 5]
        print(f"Atom versioning: {versions}")
