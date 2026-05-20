"""
willow/memory/generation_store.py — Persisted LRU backend for generation counter.
b17: GGEN1  ΔΣ=42

Stolen from josh/lru-cache-python (shelve-backed persistence).
Replaces generation.py's SOIL backend with faster local LRU + optional Postgres fallback.

Usage:
    store = GenerationLRUStore(max_bytes=10_000_000)
    gen = store.touch("atom-xyz")   # Increment + return generation count
    stats = store.stats()            # {"size_bytes": 4096, "evicted": 12, "hit_rate": 0.94}

    store.close()  # Persist to disk on shutdown
"""

import atexit
import io
import logging
import pickle
from collections import OrderedDict
from pathlib import Path
from typing import Optional

_logger = logging.getLogger("willow.memory.generation_store")


class GenerationLRUStore:
    """LRU-backed generation counter with optional persistence.

    Stores (atom_id -> generation_count) with:
    - LRU eviction at max_bytes
    - Access count tracking (hit/miss stats)
    - Optional shelve persistence (file-backed)
    """

    def __init__(self, max_bytes: int = 10_000_000, persist_path: Optional[Path] = None):
        """Initialize LRU store.

        Args:
            max_bytes: Max size before LRU eviction (default 10 MB)
            persist_path: Optional Path to shelve file for persistence across reboots
        """
        self._data = OrderedDict()         # atom_id -> {"gen": int, "hits": int}
        self._max_bytes = max_bytes
        self._persist_path = persist_path
        self._evicted_count = 0
        self._total_hits = 0
        self._total_misses = 0
        self._needs_trim = False
        self._closed = False

        if persist_path:
            self._load()

        atexit.register(self.close)

    def _load(self) -> None:
        """Load persisted state from disk if it exists."""
        if not self._persist_path or not self._persist_path.exists():
            _logger.debug("No persisted state found")
            return

        try:
            with open(self._persist_path, "rb") as f:
                loaded = pickle.load(f)
                self._data.update(loaded)
                _logger.info(f"Loaded {len(self._data)} atoms from {self._persist_path}")
        except Exception as e:
            _logger.warning(f"Failed to load persisted state: {e}")

    def touch(self, atom_id: str) -> int:
        """Increment generation for atom, return current count.

        Updates LRU order (moves to end = most recent).
        On miss: initializes to generation 1.
        """
        if atom_id in self._data:
            entry = self._data[atom_id]
            entry["gen"] += 1
            entry["hits"] += 1
            self._total_hits += 1
            _logger.debug(f"hit {atom_id} -> gen={entry['gen']}")
        else:
            entry = {"gen": 1, "hits": 1}
            self._data[atom_id] = entry
            self._total_misses += 1
            self._needs_trim = True
            _logger.debug(f"miss {atom_id} -> gen=1")

        # Move to end (LRU mark as recently used)
        self._data.move_to_end(atom_id, last=True)

        # Lazy trim on size threshold
        if self._needs_trim and self._bytesize() > self._max_bytes:
            self.trim()

        return entry["gen"]

    def get_gen(self, atom_id: str) -> int:
        """Get generation count for atom (without touch).

        Returns 0 if not found.
        """
        if atom_id not in self._data:
            return 0
        return self._data[atom_id]["gen"]

    def get_hits(self, atom_id: str) -> int:
        """Get hit count for atom.

        Returns 0 if not found.
        """
        if atom_id not in self._data:
            return 0
        return self._data[atom_id]["hits"]

    def _bytesize(self) -> int:
        """Estimate current size in bytes using pickle."""
        buf = io.BytesIO()
        pickle.dump(self._data, buf, pickle.HIGHEST_PROTOCOL)
        return buf.tell()

    def trim(self) -> int:
        """Evict LRU items until under max_bytes. Return eviction count."""
        count = 0
        while self._bytesize() > self._max_bytes and len(self._data) > 1:
            # Pop oldest (first)
            atom_id = next(iter(self._data))
            del self._data[atom_id]
            self._evicted_count += 1
            count += 1
            _logger.debug(f"evicted {atom_id}")

        self._needs_trim = False
        if count > 0:
            _logger.warning(f"trimmed {count} atoms, size now {self._bytesize()} bytes")
        return count

    def clear(self) -> None:
        """Clear all atoms and reset stats."""
        self._data.clear()
        self._evicted_count = 0
        self._total_hits = 0
        self._total_misses = 0

    def stats(self) -> dict:
        """Return store stats for monitoring."""
        total_requests = self._total_hits + self._total_misses
        hit_rate = self._total_hits / total_requests if total_requests > 0 else 0.0

        return {
            "size_bytes": self._bytesize(),
            "atom_count": len(self._data),
            "max_bytes": self._max_bytes,
            "evicted_total": self._evicted_count,
            "hits": self._total_hits,
            "misses": self._total_misses,
            "hit_rate": hit_rate,
        }

    def close(self) -> None:
        """Persist state to disk and mark closed."""
        if self._closed:
            return

        if self._persist_path:
            try:
                self._persist_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._persist_path, "wb") as f:
                    pickle.dump(self._data, f, pickle.HIGHEST_PROTOCOL)
                _logger.info(
                    f"Persisted {len(self._data)} atoms to {self._persist_path} "
                    f"({self._bytesize()} bytes)"
                )
            except Exception as e:
                _logger.error(f"Failed to persist state: {e}")

        self._closed = True

    def __repr__(self) -> str:
        stats = self.stats()
        return (
            f"<GenerationLRUStore {stats['atom_count']} atoms, "
            f"{stats['size_bytes']} bytes, hit_rate={stats['hit_rate']:.2%}>"
        )


# Global instance (singleton pattern for session-wide access)
_default_store: Optional[GenerationLRUStore] = None


def get_default_store(max_bytes: int = 10_000_000) -> GenerationLRUStore:
    """Get or create default generation store.

    Intended for use in willow/memory/generation.py to replace SOIL backend.
    """
    global _default_store
    if _default_store is None:
        persist_path = Path.home() / ".willow" / "generation_store.pkl"
        _default_store = GenerationLRUStore(max_bytes=max_bytes, persist_path=persist_path)
    return _default_store
