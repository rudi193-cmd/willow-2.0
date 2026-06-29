"""CI retrieval gold fixture — seed atoms into willow_20_test and evaluate."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from willow.bench.retrieval_gold import run_gold_set

CI_GOLD_PATH = Path(__file__).with_name("retrieval_gold_ci.json")


def load_ci_fixture(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or CI_GOLD_PATH).read_text(encoding="utf-8"))


def seed_ci_gold(pg: Any, *, path: Path | None = None) -> int:
    """Idempotently upsert CI gold atoms via knowledge_put."""
    fixture = load_ci_fixture(path)
    atoms = fixture.get("seed_atoms") or []
    for row in atoms:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        pg.knowledge_put(
            {
                "id": row["id"],
                "title": row.get("title", ""),
                "summary": row.get("summary", ""),
                "category": row.get("category", "ci-gold"),
                "source_type": row.get("source_type", "ci_seed"),
                "tier": row.get("tier", "canonical"),
                "project": row.get("project", "willow"),
                "content": row.get("content") or {},
            }
        )
    return len(atoms)


def run_ci_gold_set(pg: Any, *, path: Path | None = None) -> dict[str, Any]:
    gold_path = path or CI_GOLD_PATH
    seed_ci_gold(pg, path=gold_path)
    return run_gold_set(pg, path=gold_path)
