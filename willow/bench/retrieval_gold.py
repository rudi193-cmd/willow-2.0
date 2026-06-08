"""Fleet retrieval gold-query benchmark (read-only)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_GOLD_PATH = Path(__file__).with_name("retrieval_gold.json")


@dataclass(frozen=True)
class GoldQuery:
    id: str
    query: str
    expect_ids: tuple[str, ...]
    expect_title_contains: tuple[str, ...]
    k: int
    semantic: bool


def load_gold_queries(path: Path | None = None) -> tuple[list[GoldQuery], float]:
    raw = json.loads((path or _GOLD_PATH).read_text(encoding="utf-8"))
    min_pass_ratio = float(raw.get("min_pass_ratio", 0.71))
    queries: list[GoldQuery] = []
    for item in raw.get("queries", []):
        if not isinstance(item, dict):
            continue
        queries.append(
            GoldQuery(
                id=str(item.get("id") or item.get("query") or "query"),
                query=str(item["query"]),
                expect_ids=tuple(str(x) for x in item.get("expect_ids") or []),
                expect_title_contains=tuple(
                    str(x) for x in item.get("expect_title_contains") or []
                ),
                k=int(item.get("k", 5)),
                semantic=bool(item.get("semantic", True)),
            )
        )
    return queries, min_pass_ratio


def _atom_matches(atom: dict[str, Any], query: GoldQuery) -> bool:
    atom_id = str(atom.get("id") or "")
    title = str(atom.get("title") or "").lower()
    if query.expect_ids and atom_id in query.expect_ids:
        return True
    for fragment in query.expect_title_contains:
        if fragment.lower() in title:
            return True
    return False


def hit_rank(knowledge: list[dict[str, Any]], query: GoldQuery) -> int | None:
    for index, atom in enumerate(knowledge[: query.k]):
        if _atom_matches(atom, query):
            return index + 1
    return None


def search_knowledge(pg: Any, query: GoldQuery) -> list[dict[str, Any]]:
    if query.semantic:
        try:
            return pg.knowledge_search_semantic(query.query, limit=query.k)
        except Exception:
            return pg.knowledge_search(query.query, limit=query.k)
    return pg.knowledge_search(query.query, limit=query.k)


def evaluate_query(pg: Any, query: GoldQuery) -> dict[str, Any]:
    knowledge = search_knowledge(pg, query)
    rank = hit_rank(knowledge, query)
    top_ids = [str(row.get("id") or "") for row in knowledge[: query.k]]
    return {
        "id": query.id,
        "query": query.query,
        "semantic": query.semantic,
        "k": query.k,
        "hit": rank is not None,
        "rank": rank,
        "top_ids": top_ids,
    }


def run_gold_set(pg: Any, *, path: Path | None = None) -> dict[str, Any]:
    queries, min_pass_ratio = load_gold_queries(path)
    results = [evaluate_query(pg, query) for query in queries]
    passed = sum(1 for row in results if row["hit"])
    total = len(results)
    ratio = (passed / total) if total else 0.0
    gate = ratio >= min_pass_ratio if total else True
    return {
        "pass": gate,
        "passed": passed,
        "total": total,
        "ratio": round(ratio, 3),
        "min_pass_ratio": min_pass_ratio,
        "results": results,
    }
