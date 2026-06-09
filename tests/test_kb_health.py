"""Tests for KB health/repair utilities."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    ps = str(p)
    if ps not in sys.path:
        sys.path.insert(0, ps)

from core.kb_health import classify_preflight, graph_metrics  # noqa: E402
from core.kb_repair import (  # noqa: E402
    find_dangling_edges,
    find_duplicate_title_groups,
    find_exact_duplicate_groups,
    repair_delete_dangling,
)
from core.pg_bridge import PgBridge, run_migrations  # noqa: E402


@pytest.fixture
def pg():
    bridge = PgBridge()
    run_migrations(bridge.conn)
    yield bridge
    bridge.close()


def test_graph_metrics_shape(pg):
    metrics = graph_metrics(pg.conn)
    for key in (
        "atoms",
        "edges",
        "components",
        "dangling_edges",
        "duplicate_title_groups",
        "exact_content_duplicate_groups",
    ):
        assert key in metrics
    assert metrics["components"] >= 1
    assert metrics["atoms"] >= 1


def test_classify_preflight_pass_on_clean_graph():
    graph = {
        "components": 1,
        "dangling_edges": 0,
        "duplicate_title_groups": 0,
        "exact_content_duplicate_groups": 0,
        "degree_le1": 0,
        "degree_2": 0,
    }
    embedding = {"knowledge_embed_semantic": {"pass": True}}
    consolidation = {"pass": True, "proposed_dedup": 0}
    result = classify_preflight(graph, embedding, consolidation)
    assert result["status"] in {"PASS", "WARN"}


def test_repair_delete_dangling_dry_run(pg):
    result = repair_delete_dangling(pg.conn, apply=False)
    assert result["dry_run"] is True
    assert "found" in result


def test_find_duplicate_groups_readonly(pg):
    titles = find_duplicate_title_groups(pg.conn)
    exact = find_exact_duplicate_groups(pg.conn)
    dangling = find_dangling_edges(pg.conn)
    assert isinstance(titles, list)
    assert isinstance(exact, list)
    assert isinstance(dangling, list)


def test_kb_preflight_script_runs():
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "kb_preflight.py"), "--json-only"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )
    assert proc.returncode in (0, 1)
    payload = json.loads(proc.stdout)
    assert "summary" in payload
    assert "graph" in payload
