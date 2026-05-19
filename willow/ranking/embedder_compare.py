"""
willow/ranking/embedder_compare.py — Side-by-side embedding model comparison CLI.
b17: RANK2  ΔΣ=42

Steal track: S1LV4/th0th  (MIT License)

th0th uses bge-m3 (1024-dim via BAAI/bge-m3) while Willow currently uses
nomic-embed-text (768-dim via Ollama).  th0th's provider.ts abstraction makes
it trivial to swap models and compare quality.

This CLI tool runs a query against both models and shows side-by-side ranked
results from Willow's knowledge table, letting you evaluate whether migrating
from nomic (768d) to a higher-dim model is worthwhile before committing.

Usage (from willow-2.0 root):
    python -m willow.ranking.embedder_compare "hybrid search fallback chain"
    python -m willow.ranking.embedder_compare "embed query" --limit 5 --project hanuman
    python -m willow.ranking.embedder_compare "..." --model-a nomic-embed-text --model-b mxbai-embed-large

Models must be available in Ollama.  Check with:
    ollama list

Output:
    Table of top-N results for each model with rank, score, title, domain.
    Overlap score: how many results appear in both top-N lists.
    First-hit agreement: whether both models return the same #1 result.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Optional


# ── Embed via Ollama ──────────────────────────────────────────────────────────

def _embed_via_ollama(text: str, model: str) -> Optional[list[float]]:
    """
    Call the Ollama /api/embed endpoint directly.

    We bypass the PgBridge embed() helper so we can specify the model name.
    PgBridge.embed() always uses the configured default (nomic-embed-text).
    """
    import json
    import urllib.request

    payload = json.dumps({"model": model, "input": text}).encode()
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        embeddings = data.get("embeddings")
        if embeddings and isinstance(embeddings, list):
            return embeddings[0]
        return None
    except Exception as exc:
        print(f"[embed error] {model}: {exc}", file=sys.stderr)
        return None


# ── pgvector search with arbitrary vector ────────────────────────────────────

def _pgvector_search(
    vec: list[float],
    *,
    project: Optional[str],
    limit: int,
) -> list[dict]:
    """
    Raw pgvector ANN search using a pre-computed embedding vector.
    Returns rows ordered by cosine similarity descending.

    The knowledge.embedding column is vector(768).  If the query vector has a
    different dimension (e.g. 1024 from bge-m3), Postgres will reject the cast.
    In that case this function returns an empty list and prints a warning —
    the comparison still shows results for the model whose dimension matches.
    """
    try:
        import psycopg2  # type: ignore
        import psycopg2.extras  # type: ignore
        import os

        dsn = os.environ.get(
            "WILLOW_PG_DSN",
            "dbname=willow_20 host=localhost",
        )
        conn = psycopg2.connect(dsn)
        conn.autocommit = True

        filters = ["embedding IS NOT NULL", "invalid_at IS NULL"]
        params: list = []

        if project:
            filters.append("project = %s")
            params.append(project)

        where = " AND ".join(filters)
        vec_str = str(vec)

        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT id, title, summary, project, weight,"
                    f" 1 - (embedding <=> %s::vector) AS _sim"
                    f" FROM knowledge WHERE {where}"
                    f" ORDER BY embedding <=> %s::vector ASC LIMIT %s",
                    [vec_str] + params + [vec_str, limit],
                )
                return [dict(r) for r in cur.fetchall()]
        except psycopg2.errors.DataException as dim_err:
            print(
                f"  [dim mismatch] vector({len(vec)}) vs knowledge.embedding vector(768): {dim_err}",
                file=sys.stderr,
            )
            return []
        finally:
            conn.close()

    except Exception as exc:
        print(f"[pg error] {exc}", file=sys.stderr)
        return []


# ── Formatting ────────────────────────────────────────────────────────────────

def _truncate(text: str, n: int) -> str:
    if not text:
        return ""
    return text[:n] + ("…" if len(text) > n else "")


def _print_results(
    model: str,
    dim: int,
    results: list[dict],
    elapsed_ms: float,
) -> None:
    print(f"\n  Model : {model} ({dim}d)  [{elapsed_ms:.0f} ms]")
    print(f"  {'Rank':<5}  {'Score':>6}  {'Domain':<12}  Title")
    print(f"  {'----':<5}  {'-----':>6}  {'------':<12}  -----")
    for i, r in enumerate(results, 1):
        score = r.get("_sim") or 0.0
        domain = _truncate(str(r.get("project") or ""), 12)
        title = _truncate(str(r.get("title") or r.get("id") or "?"), 55)
        print(f"  {i:<5}  {score:>6.4f}  {domain:<12}  {title}")


def _overlap(a: list[dict], b: list[dict]) -> int:
    ids_a = {r["id"] for r in a}
    ids_b = {r["id"] for r in b}
    return len(ids_a & ids_b)


# ── Main ──────────────────────────────────────────────────────────────────────

def compare(
    query: str,
    *,
    model_a: str = "nomic-embed-text",
    model_b: str = "mxbai-embed-large",
    project: Optional[str] = None,
    limit: int = 10,
) -> None:
    """Run query through two Ollama models and show side-by-side KB results."""

    print(f"\nQuery     : {query!r}")
    print(f"Project   : {project or '(all)'}")
    print(f"Limit     : {limit}")
    print(f"Models    : {model_a}  vs  {model_b}")
    print("=" * 80)

    # Model A
    t0 = time.monotonic()
    vec_a = _embed_via_ollama(query, model_a)
    embed_ms_a = (time.monotonic() - t0) * 1000

    if vec_a is None:
        print(f"\n  [{model_a}] embedding failed — is the model loaded in Ollama?")
        results_a: list[dict] = []
        dim_a = 0
    else:
        dim_a = len(vec_a)
        t1 = time.monotonic()
        results_a = _pgvector_search(vec_a, project=project, limit=limit)
        search_ms_a = (time.monotonic() - t1) * 1000
        _print_results(model_a, dim_a, results_a, embed_ms_a + search_ms_a)

    # Model B
    t0 = time.monotonic()
    vec_b = _embed_via_ollama(query, model_b)
    embed_ms_b = (time.monotonic() - t0) * 1000

    if vec_b is None:
        print(f"\n  [{model_b}] embedding failed — is the model loaded in Ollama?")
        results_b: list[dict] = []
        dim_b = 0
    else:
        dim_b = len(vec_b)
        t1 = time.monotonic()
        results_b = _pgvector_search(vec_b, project=project, limit=limit)
        search_ms_b = (time.monotonic() - t1) * 1000
        _print_results(model_b, dim_b, results_b, embed_ms_b + search_ms_b)

    # Agreement summary
    if results_a and results_b:
        n_overlap = _overlap(results_a, results_b)
        first_agree = results_a[0]["id"] == results_b[0]["id"]
        print(f"\n  Overlap (top-{limit})  : {n_overlap}/{limit} atoms in common")
        print(f"  First-hit agreement : {'YES' if first_agree else 'NO'}")
        if not first_agree:
            print(f"    {model_a} #1 → {_truncate(results_a[0].get('title','?'), 50)}")
            print(f"    {model_b} #1 → {_truncate(results_b[0].get('title','?'), 50)}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare two Ollama embedding models on Willow KB results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("query", help="Search query string")
    parser.add_argument(
        "--model-a", default="nomic-embed-text",
        help="First Ollama model (default: nomic-embed-text)",
    )
    parser.add_argument(
        "--model-b", default="mxbai-embed-large",
        help="Second Ollama model (default: mxbai-embed-large)",
    )
    parser.add_argument(
        "--project", default=None,
        help="Restrict to atoms with this project value",
    )
    parser.add_argument(
        "--limit", type=int, default=10,
        help="Number of results per model (default: 10)",
    )
    args = parser.parse_args()

    compare(
        args.query,
        model_a=args.model_a,
        model_b=args.model_b,
        project=args.project,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
