"""
willow/memory/generation.py — generation-counter aware fact store.

Stolen from moonshine's observer/reflect.js generation + supersedure model.
Adapted for Willow's SOIL backend (store_put / store_get / store_search via MCP).

## What moonshine does
Each observation starts at generation=0. After the Observer extracts facts,
the Reflector condenses the set: it increments generation on surviving facts
and soft-tombstones superseded ones (sets superseded_at). Facts not referenced
across N generations are implicitly dead — they fall out of search because
superseded facts are excluded from active indexes.

## What we do here
We implement the same pattern over SOIL (Postgres-backed KV store) instead of
SQLite. Each SOIL record in a "generation-tracked" collection gets:
  - generation:   int  — incremented each time the fact survives a reflection pass
  - superseded_by: str | None  — ID of the fact that replaced this one
  - superseded_at: ISO str | None  — when supersedure was recorded
  - last_seen_gen: int  — the last global generation pass that referenced this fact

The "global generation counter" lives as a single SOIL record:
  collection: {agent}/memory/gen_counter
  id: "global"
  value: int

Usage:

    from willow.memory.generation import GenerationStore

    gs = GenerationStore(agent=require_agent_name(), mcp_call=call)

    # Write a new fact
    fact_id = gs.put_fact({
        "id": "my-fact-123",
        "title": "Sean prefers Postgres over SQLite for production",
        "content": "...",
        "type": "preference",
        "importance": 4,
    })

    # Mark fact as referenced (bumps last_seen_gen)
    gs.touch(fact_id)

    # Run a reflection pass: demote facts not seen in the last N generations
    demoted = gs.demote_stale(max_unseen_generations=3)

    # Supersede one fact with another (moonshine's soft-tombstone)
    gs.supersede(old_id="my-fact-123", new_id="my-fact-456")

    # Query only active (non-superseded) facts
    active = gs.list_active(limit=50)
"""

from __future__ import annotations

import logging
import os
from core.agent_identity import require_agent_name
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger("willow.memory.generation")

# Collection names follow Willow's agent/topic pattern
_GEN_COUNTER_COLLECTION = "{agent}/memory/gen_counter"
_FACTS_COLLECTION = "{agent}/memory/facts"

_GLOBAL_COUNTER_ID = "global"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GenerationStore:
    """
    Generation-counter aware fact store wrapping SOIL via MCP.

    Parameters
    ----------
    agent:
        Agent namespace (e.g. "hanuman"). All SOIL keys are scoped under it.
    mcp_call:
        Callable matching Willow's ``call(tool, params, timeout)`` signature.
        Typically ``from willow.fylgja._mcp import call``.
    timeout:
        Per-MCP-call timeout in seconds (default 6).
    """

    def __init__(
        self,
        agent: str,
        mcp_call: Callable,
        timeout: int = 6,
    ) -> None:
        self.agent = agent
        self._call = mcp_call
        self._timeout = timeout
        self._facts_coll = _FACTS_COLLECTION.format(agent=agent)
        self._counter_coll = _GEN_COUNTER_COLLECTION.format(agent=agent)

    # ------------------------------------------------------------------
    # Global generation counter
    # ------------------------------------------------------------------

    def current_generation(self) -> int:
        """Return the current global generation counter (0 if uninitialised)."""
        try:
            rec = self._call(
                "store_get",
                {"app_id": self.agent, "collection": self._counter_coll, "id": _GLOBAL_COUNTER_ID},
                timeout=self._timeout,
            )
            return int(rec.get("value", 0)) if rec else 0
        except Exception:
            return 0

    def _increment_generation(self) -> int:
        """Bump the global counter and return the new value."""
        new_gen = self.current_generation() + 1
        try:
            self._call(
                "store_put",
                {
                    "app_id": self.agent,
                    "collection": self._counter_coll,
                    "record": {
                        "id": _GLOBAL_COUNTER_ID,
                        "value": new_gen,
                        "updated_at": _now_iso(),
                    },
                },
                timeout=self._timeout,
            )
        except Exception as exc:
            logger.warning("generation counter increment failed: %s", exc)
        return new_gen

    # ------------------------------------------------------------------
    # Fact write / touch
    # ------------------------------------------------------------------

    def put_fact(self, fact: dict[str, Any]) -> str:
        """
        Write a new fact into the generation-tracked collection.

        ``fact`` must include an ``id`` field. Missing generation fields are
        injected automatically:
          - generation = 0
          - last_seen_gen = current_generation()
          - superseded_by = None
          - superseded_at = None
          - created_at = now (if absent)

        Returns the fact id.
        """
        fact = dict(fact)  # don't mutate caller's dict
        if "id" not in fact:
            raise ValueError("fact must have an 'id' field")

        gen = self.current_generation()
        fact.setdefault("generation", 0)
        fact.setdefault("last_seen_gen", gen)
        fact.setdefault("superseded_by", None)
        fact.setdefault("superseded_at", None)
        fact.setdefault("created_at", _now_iso())
        fact["updated_at"] = _now_iso()

        try:
            self._call(
                "store_put",
                {"app_id": self.agent, "collection": self._facts_coll, "record": fact},
                timeout=self._timeout,
            )
        except Exception as exc:
            logger.warning("put_fact failed for %s: %s", fact["id"], exc)

        return fact["id"]

    def touch(self, fact_id: str) -> None:
        """
        Mark a fact as referenced in the current generation pass.

        Fetches the existing record, bumps ``last_seen_gen`` to the current
        generation counter, writes back. Used during retrieval so that actively
        queried facts don't decay.
        """
        try:
            rec = self._call(
                "store_get",
                {"app_id": self.agent, "collection": self._facts_coll, "id": fact_id},
                timeout=self._timeout,
            )
            if not rec:
                return
            rec["last_seen_gen"] = self.current_generation()
            rec["updated_at"] = _now_iso()
            self._call(
                "store_put",
                {"app_id": self.agent, "collection": self._facts_coll, "record": rec},
                timeout=self._timeout,
            )
        except Exception as exc:
            logger.warning("touch failed for %s: %s", fact_id, exc)

    # ------------------------------------------------------------------
    # Reflection pass: supersedure + demotion
    # ------------------------------------------------------------------

    def supersede(self, old_id: str, new_id: str) -> None:
        """
        Soft-tombstone ``old_id`` and point it at ``new_id``.

        Mirrors moonshine reflector's superseded_ids mechanism. The old fact
        stays in SOIL (archive, not delete) but is excluded from active queries
        because ``superseded_at`` is set.
        """
        try:
            rec = self._call(
                "store_get",
                {"app_id": self.agent, "collection": self._facts_coll, "id": old_id},
                timeout=self._timeout,
            )
            if not rec:
                logger.warning("supersede: fact %s not found", old_id)
                return
            rec["superseded_by"] = new_id
            rec["superseded_at"] = _now_iso()
            rec["updated_at"] = _now_iso()
            self._call(
                "store_put",
                {"app_id": self.agent, "collection": self._facts_coll, "record": rec},
                timeout=self._timeout,
            )
        except Exception as exc:
            logger.warning("supersede failed (%s → %s): %s", old_id, new_id, exc)

    def demote_stale(self, max_unseen_generations: int = 3) -> list[str]:
        """
        Demote facts not referenced in the last ``max_unseen_generations`` passes.

        A fact is stale when:
            current_generation - fact.last_seen_gen > max_unseen_generations

        Stale facts are soft-tombstoned with ``superseded_by = "DEMOTED"`` so
        downstream search (which filters ``superseded_at IS NULL``) drops them
        automatically. They remain queryable via ``list_all`` for archival.

        Returns a list of demoted fact IDs.

        NOTE: Requires ``store_search`` to support listing all records in a
        collection (query=""). If the collection is large, call this on a
        background schedule, not inline with user requests.
        """
        current_gen = self.current_generation()
        cutoff_gen = current_gen - max_unseen_generations

        demoted: list[str] = []
        try:
            all_facts = self._call(
                "store_search",
                {
                    "app_id": self.agent,
                    "collection": self._facts_coll,
                    "query": "",
                    "limit": 500,
                },
                timeout=self._timeout,
            ) or []
        except Exception as exc:
            logger.warning("demote_stale: store_search failed: %s", exc)
            return demoted

        for fact in all_facts:
            # Skip already-tombstoned facts
            if fact.get("superseded_at"):
                continue
            last_seen = fact.get("last_seen_gen", 0)
            if last_seen < cutoff_gen:
                fact_id = fact.get("id")
                if not fact_id:
                    continue
                try:
                    fact["superseded_by"] = "DEMOTED"
                    fact["superseded_at"] = _now_iso()
                    fact["updated_at"] = _now_iso()
                    self._call(
                        "store_put",
                        {"app_id": self.agent, "collection": self._facts_coll, "record": fact},
                        timeout=self._timeout,
                    )
                    demoted.append(fact_id)
                    logger.info(
                        "demoted fact %s (last_seen_gen=%d, current=%d)",
                        fact_id, last_seen, current_gen,
                    )
                except Exception as exc:
                    logger.warning("demote_stale: put failed for %s: %s", fact_id, exc)

        return demoted

    def run_reflection_pass(
        self,
        surviving_ids: list[str],
        superseded_ids: list[str],
        *,
        max_unseen_generations: int = 3,
    ) -> dict[str, Any]:
        """
        Full moonshine-style reflection pass.

        Call this after your LLM condenser produces a new condensed set.

        1. Increment the global generation counter.
        2. Touch all surviving facts (updates last_seen_gen).
        3. Supersede all explicitly superseded facts.
        4. Run stale demotion (generation-decay sweep).

        Returns a summary dict.
        """
        new_gen = self._increment_generation()

        for fid in surviving_ids:
            self.touch(fid)

        for fid in superseded_ids:
            # Find what replaced it — caller should have already written the
            # new fact and passed its id in surviving_ids.
            self.supersede(fid, new_id="condensed")

        demoted = self.demote_stale(max_unseen_generations=max_unseen_generations)

        return {
            "new_generation": new_gen,
            "surviving": len(surviving_ids),
            "superseded": len(superseded_ids),
            "demoted": len(demoted),
            "demoted_ids": demoted,
        }

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def list_active(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return facts that have not been superseded."""
        try:
            all_facts = self._call(
                "store_search",
                {
                    "app_id": self.agent,
                    "collection": self._facts_coll,
                    "query": "",
                    "limit": limit * 2,  # over-fetch to compensate for filtered-out tombstones
                },
                timeout=self._timeout,
            ) or []
        except Exception as exc:
            logger.warning("list_active: store_search failed: %s", exc)
            return []

        active = [f for f in all_facts if not f.get("superseded_at")]
        return active[:limit]

    def list_all(self, limit: int = 200) -> list[dict[str, Any]]:
        """Return all facts including tombstoned ones (for archival / audit)."""
        try:
            return self._call(
                "store_search",
                {
                    "app_id": self.agent,
                    "collection": self._facts_coll,
                    "query": "",
                    "limit": limit,
                },
                timeout=self._timeout,
            ) or []
        except Exception as exc:
            logger.warning("list_all: store_search failed: %s", exc)
            return []

    def stats(self) -> dict[str, int]:
        """Return generation stats: current generation, active count, tombstoned count."""
        all_facts = self.list_all(limit=1000)
        active = [f for f in all_facts if not f.get("superseded_at")]
        tombstoned = [f for f in all_facts if f.get("superseded_at")]
        demoted = [f for f in tombstoned if f.get("superseded_by") == "DEMOTED"]
        return {
            "current_generation": self.current_generation(),
            "total": len(all_facts),
            "active": len(active),
            "tombstoned": len(tombstoned),
            "demoted": len(demoted),
            "superseded": len(tombstoned) - len(demoted),
        }
