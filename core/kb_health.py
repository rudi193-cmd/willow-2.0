"""kb_health.py — shared graph integrity and readiness metrics for KB maintenance."""

from __future__ import annotations

import collections
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent

_SKIP_PROJECTS = (
    "session-turn",
    "conversation",
    "file_location",
    "die-namic-index",
    "willow_index",
    "sessions",
    "telemetry",
    "training",
)
_MIN_TEXT = 20


def skip_projects_sql() -> str:
    return ", ".join(f"'{p}'" for p in _SKIP_PROJECTS)


def graph_metrics(conn) -> dict[str, Any]:
    """Compute graph integrity metrics from Postgres."""
    cur = conn.cursor()
    cur.execute("SET statement_timeout = '120s'")

    cur.execute("SELECT count(*) FROM knowledge WHERE invalid_at IS NULL")
    atoms = int(cur.fetchone()[0])

    cur.execute("SELECT count(*) FROM edges")
    edges = int(cur.fetchone()[0])

    cur.execute(
        """
        SELECT count(*) FROM edges e
        WHERE NOT EXISTS(
            SELECT 1 FROM knowledge k WHERE k.id = e.from_id AND k.invalid_at IS NULL
        ) OR NOT EXISTS(
            SELECT 1 FROM knowledge k WHERE k.id = e.to_id AND k.invalid_at IS NULL
        )
        """
    )
    dangling = int(cur.fetchone()[0])

    cur.execute(
        """
        WITH edge_deg AS (
          SELECT id, count(*) AS d FROM (
            SELECT from_id AS id FROM edges
            UNION ALL
            SELECT to_id AS id FROM edges
          ) u GROUP BY id
        )
        SELECT
          sum(CASE WHEN coalesce(e.d, 0) <= 1 THEN 1 ELSE 0 END),
          sum(CASE WHEN coalesce(e.d, 0) = 2 THEN 1 ELSE 0 END)
        FROM knowledge k
        LEFT JOIN edge_deg e ON e.id = k.id
        WHERE k.invalid_at IS NULL
        """
    )
    deg_le1, deg2 = cur.fetchone()
    deg_le1 = int(deg_le1 or 0)
    deg2 = int(deg2 or 0)

    cur.execute(
        """
        SELECT count(*) FROM (
          SELECT lower(title) FROM knowledge
          WHERE invalid_at IS NULL AND title IS NOT NULL
          GROUP BY lower(title) HAVING count(*) > 1
        ) d
        """
    )
    dup_title_groups = int(cur.fetchone()[0])

    cur.execute(
        """
        WITH sigs AS (
          SELECT project, source_type, lower(title) AS ltitle,
                 coalesce(summary, '') AS summary,
                 coalesce(content::text, '') AS content_text,
                 count(*) AS c
          FROM knowledge
          WHERE invalid_at IS NULL AND title IS NOT NULL
          GROUP BY project, source_type, lower(title), coalesce(summary, ''), coalesce(content::text, '')
          HAVING count(*) > 1
        )
        SELECT count(*), coalesce(sum(c - 1), 0) FROM sigs
        """
    )
    exact_groups, exact_redundant = cur.fetchone()
    exact_groups = int(exact_groups or 0)
    exact_redundant = int(exact_redundant or 0)

    cur.execute("SELECT from_id, to_id FROM edges")
    adj: dict[str, set[str]] = collections.defaultdict(set)
    for a, b in cur.fetchall():
        adj[a].add(b)
        adj[b].add(a)

    cur.execute("SELECT id FROM knowledge WHERE invalid_at IS NULL")
    all_ids = [r[0] for r in cur.fetchall()]
    for aid in all_ids:
        adj.setdefault(aid, set())

    seen: set[str] = set()
    components = 0
    largest = 0
    for start in all_ids:
        if start in seen:
            continue
        components += 1
        stack = [start]
        size = 0
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            size += 1
            stack.extend(adj[n] - seen)
        largest = max(largest, size)

    density = round(edges / atoms, 4) if atoms else 0.0

    return {
        "atoms": atoms,
        "edges": edges,
        "density": density,
        "components": components,
        "largest_component": largest,
        "dangling_edges": dangling,
        "degree_le1": deg_le1,
        "degree_2": deg2,
        "duplicate_title_groups": dup_title_groups,
        "exact_content_duplicate_groups": exact_groups,
        "exact_content_redundant_atoms": exact_redundant,
    }


def embedding_completeness(conn, threshold: float = 96.0) -> dict[str, Any]:
    """Run embedding completeness checks (mirrors pg_completeness_gate knowledge metrics)."""
    skip_in = skip_projects_sql()
    cur = conn.cursor()
    checks: dict[str, Any] = {}

    cur.execute(
        f"""
        WITH base AS (
          SELECT embedding IS NOT NULL AS has_e,
                 length(trim(coalesce(title, '') || ' ' || coalesce(summary, ''))) AS txtlen
          FROM public.knowledge
          WHERE invalid_at IS NULL AND project NOT IN ({skip_in})
        )
        SELECT
          count(*) FILTER (WHERE txtlen >= {_MIN_TEXT}) AS total,
          count(*) FILTER (WHERE txtlen >= {_MIN_TEXT} AND has_e) AS embedded
        FROM base
        """
    )
    total, embedded = cur.fetchone()
    total = int(total or 0)
    embedded = int(embedded or 0)
    pct = round(100.0 * embedded / total, 4) if total else 100.0
    checks["knowledge_embed_semantic"] = {
        "pct": pct,
        "embedded": embedded,
        "total": total,
        "pass": pct >= threshold,
    }

    cur.execute(
        f"""
        SELECT
          count(*) AS total,
          count(*) FILTER (WHERE
            embedding IS NOT NULL
            OR length(trim(coalesce(title, '') || ' ' || coalesce(summary, ''))) < {_MIN_TEXT}
            OR project IN ({skip_in})
          ) AS satisfied
        FROM public.knowledge
        WHERE invalid_at IS NULL
        """
    )
    vtotal, vsatisfied = cur.fetchone()
    vtotal = int(vtotal or 0)
    vsatisfied = int(vsatisfied or 0)
    vpct = round(100.0 * vsatisfied / vtotal, 4) if vtotal else 100.0
    checks["knowledge_valid_satisfied"] = {
        "pct": vpct,
        "satisfied": vsatisfied,
        "total": vtotal,
        "pass": vpct >= threshold,
    }

    return checks


def consolidation_dry_run(repo: Optional[Path] = None) -> dict[str, Any]:
    """Run sleep_consolidation dry-run and parse proposed dedup count."""
    repo = repo or _REPO
    script = repo / "scripts" / "sleep_consolidation.py"
    if not script.is_file():
        return {"error": "sleep_consolidation.py not found", "proposed_dedup": None}

    proc = subprocess.run(
        [sys.executable, str(script), "--dry-run", "--skip-intelligence"],
        capture_output=True,
        text=True,
        cwd=str(repo),
        timeout=300,
    )
    stdout = proc.stdout or ""
    proposed = 0
    for line in stdout.splitlines():
        if "Deduped:" in line:
            try:
                proposed = int(line.split("Deduped:")[1].strip().split()[0])
            except (IndexError, ValueError):
                pass
    return {
        "returncode": proc.returncode,
        "proposed_dedup": proposed,
        "pass": proposed == 0,
        "stdout_tail": stdout.strip()[-1500:],
    }


def run_preflight(threshold: float = 96.0) -> dict[str, Any]:
    """Run full KB preflight and return structured report."""
    from core.pg_bridge import PgBridge, run_migrations

    pg = PgBridge()
    run_migrations(pg.conn)
    try:
        graph = graph_metrics(pg.conn)
        embedding = embedding_completeness(pg.conn, threshold=threshold)
        consolidation = consolidation_dry_run(_REPO)
        human = _human_required(pg.conn)
        health = _health_report(_REPO)

        summary = classify_preflight(
            graph,
            embedding,
            consolidation,
            human_open=human.get("open_total", 0),
            human_high=human.get("high_priority", 0),
        )

        return {
            "summary": summary,
            "graph": graph,
            "embedding": embedding,
            "consolidation": consolidation,
            "human_required": human,
            "health": health,
        }
    finally:
        pg.close()


def _human_required(conn) -> dict[str, Any]:
    try:
        from core.human_required import list_items, stats

        summary = stats(conn)
        items = list_items(conn, status="open", limit=20)
        by_priority = summary.get("by_priority") or {}
        return {
            "stats": summary,
            "open_items": items,
            "open_total": int(summary.get("open_total") or 0),
            "high_priority": int(by_priority.get("high", 0) + by_priority.get("critical", 0)),
        }
    except Exception as exc:
        return {"error": str(exc)}


def _health_report(repo: Path) -> dict[str, Any]:
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "health_report_mod", repo / "scripts" / "health_report.py"
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return {
                "manifests": mod._manifest_report(),
                "postgres": mod._postgres_report(),
                "nest": mod._nest_triage(),
                "metabolic": mod._metabolic_report(),
                "dream": mod._dream_report(),
            }
    except Exception as exc:
        return {"error": str(exc)}
    return {"error": "health_report unavailable"}


def classify_preflight(
    graph: dict[str, Any],
    embedding: dict[str, Any],
    consolidation: dict[str, Any],
    human_open: int = 0,
    human_high: int = 0,
) -> dict[str, Any]:
    """Return PASS/WARN/FAIL summary for preflight checks."""
    failures: list[str] = []
    warnings: list[str] = []

    if graph.get("components", 0) != 1:
        failures.append(f"components={graph.get('components')} (expected 1)")
    if graph.get("dangling_edges", 0) > 0:
        failures.append(f"dangling_edges={graph.get('dangling_edges')}")
    if graph.get("duplicate_title_groups", 0) > 0:
        failures.append(f"duplicate_title_groups={graph.get('duplicate_title_groups')}")
    if graph.get("exact_content_duplicate_groups", 0) > 0:
        failures.append(f"exact_content_duplicate_groups={graph.get('exact_content_duplicate_groups')}")
    if graph.get("degree_le1", 0) > 0:
        warnings.append(f"degree_le1={graph.get('degree_le1')}")
    if graph.get("degree_2", 0) > 10:
        warnings.append(f"degree_2={graph.get('degree_2')}")

    sem = embedding.get("knowledge_embed_semantic", {})
    if not sem.get("pass", True):
        warnings.append(
            f"knowledge_embed_semantic={sem.get('pct')}% "
            f"({sem.get('embedded')}/{sem.get('total')})"
        )

    if not consolidation.get("pass", True):
        failures.append(f"consolidation_proposed_dedup={consolidation.get('proposed_dedup')}")

    if human_high > 0:
        warnings.append(f"human_required_high_priority={human_high}")
    elif human_open > 0:
        warnings.append(f"human_required_open={human_open}")

    if failures:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"

    return {"status": status, "failures": failures, "warnings": warnings}
