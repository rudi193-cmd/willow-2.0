"""store_port.py — narrow SOIL access protocol (ADR-20260616 Phase 1).

b17: STPRT · ΔΣ=42

WillowStore is the only module that opens SOIL SQLite files. Callers outside
core/willow_store.py should use StorePort (via WillowStoreAdapter or get_store_port).
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from core.willow_store import Rubric, WillowStore


@runtime_checkable
class StorePort(Protocol):
    """In-process SOIL facade — MCP, hooks (Phase 2), and core.soil shim."""

    def get(self, collection: str, record_id: str) -> Optional[dict]: ...

    def put(
        self,
        collection: str,
        record: dict,
        record_id: Optional[str] = None,
        deviation: float = 0.0,
    ) -> tuple: ...

    def update(
        self,
        collection: str,
        record_id: str,
        record: dict,
        deviation: float = 0.0,
    ) -> tuple: ...

    def delete(self, collection: str, record_id: str) -> bool: ...

    def list(self, collection: str) -> list: ...

    def all(self, collection: str) -> list: ...

    def search(self, collection: str, query: str, after: str | None = None) -> list: ...

    def search_all(self, query: str) -> list: ...

    def search_semantic(self, collection: str, query: str, limit: int = 20) -> list: ...

    def stats(self) -> dict: ...

    def edges_for(self, record_id: str) -> list: ...

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        relation: str,
        context: str = "",
    ) -> tuple: ...

    def audit_log(self, collection: str, limit: int = 20) -> list: ...


class WillowStoreAdapter:
    """Default StorePort — thin delegate over WillowStore."""

    def __init__(self, root: Optional[str] = None, rubric: Rubric | None = None):
        self._store = WillowStore(root=root, rubric=rubric)

    @property
    def backend(self) -> WillowStore:
        """Underlying WillowStore — avoid in new code; soil shim raw SQL only."""
        return self._store

    @property
    def root(self):
        return self._store.root

    def get(self, collection: str, record_id: str) -> Optional[dict]:
        return self._store.get(collection, record_id)

    def put(
        self,
        collection: str,
        record: dict,
        record_id: Optional[str] = None,
        deviation: float = 0.0,
    ) -> tuple:
        return self._store.put(collection, record, record_id=record_id, deviation=deviation)

    def update(
        self,
        collection: str,
        record_id: str,
        record: dict,
        deviation: float = 0.0,
    ) -> tuple:
        return self._store.update(collection, record_id, record, deviation=deviation)

    def delete(self, collection: str, record_id: str) -> bool:
        return self._store.delete(collection, record_id)

    def list(self, collection: str) -> list:
        return self._store.list(collection)

    def all(self, collection: str) -> list:
        return self._store.all(collection)

    def search(self, collection: str, query: str, after: str | None = None) -> list:
        return self._store.search(collection, query, after=after)

    def search_all(self, query: str) -> list:
        return self._store.search_all(query)

    def search_semantic(self, collection: str, query: str, limit: int = 20) -> list:
        return self._store.search_semantic(collection, query, limit=limit)

    def stats(self) -> dict:
        return self._store.stats()

    def edges_for(self, record_id: str) -> list:
        return self._store.edges_for(record_id)

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        relation: str,
        context: str = "",
    ) -> tuple:
        return self._store.add_edge(from_id, to_id, relation, context=context)

    def audit_log(self, collection: str, limit: int = 20) -> list:
        return self._store.audit_log(collection, limit=limit)


def get_store_port(root: Optional[str] = None, rubric: Rubric | None = None) -> WillowStoreAdapter:
    """Return the default in-process SOIL port (fresh adapter per call)."""
    return WillowStoreAdapter(root=root, rubric=rubric)
