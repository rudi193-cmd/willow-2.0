"""
Compare clean vs dirty KB run outputs against a fixed set of probe queries.

Usage:
    python -m sandbox.rh_harness.compare

Prints a side-by-side markdown table of top-5 results per query per run,
then a summary verdict: did the dirty run converge to the same canon?

Probe queries are chosen to exercise:
  1. Canonical RH path (should surface current proof strategy, not dead ends)
  2. Weil conjecture status (should surface "roughly done, needs clean pass")
  3. APO vocabulary (should surface custom terms, not flatten them)
  4. Deprecated/discarded material (dirty run only — should NOT surface these
     in top results if discernment is working)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

PROBE_QUERIES = [
    {
        "id": "rh_canon",
        "label": "Canonical RH path",
        "query": "current canonical proof strategy Riemann Hypothesis information geometric APO",
        "flag": "noise_check",  # dirty run should NOT rank deprecated iterations first
    },
    {
        "id": "weil_status",
        "label": "Weil conjecture status",
        "query": "Weil conjecture mapping status completeness APO",
        "flag": None,
    },
    {
        "id": "apo_vocab",
        "label": "APO vocabulary",
        "query": "Axioms Pattern Ontology custom terminology infogeometric",
        "flag": None,
    },
    {
        "id": "lean_proof",
        "label": "Lean 4 verification",
        "query": "Lean 4 machine checked proof mathlib RH zeta",
        "flag": None,
    },
    {
        "id": "dead_ends",
        "label": "Discarded iterations (noise probe)",
        "query": "deprecated failed iteration non-canon discard",
        "flag": "noise_check",  # dirty run: do these surface high? that's bad
    },
]


@dataclass
class RunResult:
    run_id: str
    query_id: str
    hits: list[dict] = field(default_factory=list)


def fetch_results(run_id: str) -> list[RunResult]:
    try:
        from sandbox.rh_harness.willow_shim import search_kb
    except ImportError:
        sys.exit("ERROR: willow_shim not available")

    results = []
    for probe in PROBE_QUERIES:
        hits = search_kb(probe["query"], run_id=run_id, limit=5)
        results.append(RunResult(run_id=run_id, query_id=probe["id"], hits=hits))
    return results


def render_table(clean: list[RunResult], dirty: list[RunResult]) -> str:
    lines = ["# RH Harness — Clean vs Dirty KB Comparison\n"]

    clean_by_id = {r.query_id: r for r in clean}
    dirty_by_id = {r.query_id: r for r in dirty}

    for probe in PROBE_QUERIES:
        lines.append(f"## {probe['label']}\n")
        lines.append(f"Query: `{probe['query']}`\n")
        lines.append("| Rank | Clean | Dirty |")
        lines.append("|------|-------|-------|")

        c_hits = clean_by_id[probe["id"]].hits
        d_hits = dirty_by_id[probe["id"]].hits
        for i in range(max(len(c_hits), len(d_hits), 5)):
            c = c_hits[i]["title"] if i < len(c_hits) else "—"
            d = d_hits[i]["title"] if i < len(d_hits) else "—"
            lines.append(f"| {i + 1} | {c} | {d} |")
        lines.append("")

    lines.append("## Verdict\n")
    lines.append(_verdict(clean_by_id, dirty_by_id))
    return "\n".join(lines)


def _verdict(clean: dict, dirty: dict) -> str:
    noise_probes = [p for p in PROBE_QUERIES if p["flag"] == "noise_check"]
    issues = []

    for probe in noise_probes:
        c_titles = {h["title"] for h in clean[probe["id"]].hits[:3]}
        d_titles = [h["title"] for h in dirty[probe["id"]].hits[:3]]
        for title in d_titles:
            if title not in c_titles and "deprecated" in title.lower():
                issues.append(f"- Dirty top-3 for `{probe['id']}` surfaces noise: `{title}`")

    if not issues:
        return "**PASS** — dirty run top results converge with clean on all noise-check probes."
    return "**WARN** — dirty run diverges on noise probes:\n" + "\n".join(issues)


def main() -> None:
    print("Fetching clean run results...", file=sys.stderr)
    clean = fetch_results("clean")
    print("Fetching dirty run results...", file=sys.stderr)
    dirty = fetch_results("dirty")
    print(render_table(clean, dirty))


if __name__ == "__main__":
    main()
