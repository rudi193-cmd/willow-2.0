"""
Stone soup harness — staged dry-run synthesis.

Usage:
    python3 -m sandbox.stone_soup.run
    python3 -m sandbox.stone_soup.run --output sandbox/stone_soup/reports/latest.md
    python3 -m sandbox.stone_soup.run --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sandbox.stone_soup.adapters import IngredientResult, collect_ingredient
from sandbox.stone_soup.alignment import evaluate_alignment, render_human_synthesis
from sandbox.stone_soup.layers import collect_layers

INGREDIENTS_PATH = Path(__file__).resolve().parent / "ingredients.json"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def _noise_suppression_signal() -> str | bool:
    """Live rh-dirty noise probe — no clean/dirty tag ingest required."""
    try:
        from sandbox.stone_soup.willow_shim import kb_search

        hits = kb_search(
            "deprecated failed iteration non-canon discard",
            limit=5,
            project="rh-dirty",
        )
        top = [(h.get("title") or "") for h in hits[:3]]
        noise = [t for t in top if "deprecated" in t.lower()]
        if not hits:
            return "no_hits"
        return "pass" if not noise else f"noise_in_top3:{noise[0][:80]}"
    except Exception:
        return "probe_failed"


def load_config() -> dict[str, Any]:
    return json.loads(INGREDIENTS_PATH.read_text(encoding="utf-8"))


def stage_kb_retrieval(
    ingredients: list[dict[str, Any]], *, limit: int
) -> dict[str, Any]:
    results: dict[str, IngredientResult] = {}
    for ing in ingredients:
        results[ing["id"]] = collect_ingredient(ing, limit=limit)
    return {
        "stage": "kb_retrieval",
        "ingredients": {
            iid: {
                "label": r.label,
                "visibility": r.visibility,
                "hit_count": len(r.kb_hits),
                "hits": r.kb_hits,
            }
            for iid, r in results.items()
        },
        "_raw": results,
    }


def stage_provenance(raw: dict[str, IngredientResult]) -> dict[str, Any]:
    rows = []
    for iid, r in raw.items():
        rows.append(
            {
                "id": iid,
                "label": r.label,
                "visibility": r.visibility,
                "access_notes": r.notes,
                "has_kb_signal": len(r.kb_hits) > 0,
                "has_local_structure": bool(r.structure),
                "has_governance": bool(r.governance),
            }
        )
    return {"stage": "provenance", "classifications": rows}


def canonical_reconstruction_census(*, app_id: str = "willow") -> dict[str, Any]:
    """W8 substrate: of canonical (non-benchmark) KB atoms, how many are
    reconstructable — currently via FRANK ledger atom-id references.

    Structure-only: ids and counts, never atom text. Handoff and source_trail
    support legs are declared in ``by_support`` but not yet measured, so the
    reported cost is a *ledger-only upper bound* (true coverage can only be
    higher). Raises on DB unavailability — the evaluator maps that to pending.
    """
    from core.pg_bridge import PgBridge

    pg = PgBridge()
    pg._ensure_conn()
    with pg.conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM knowledge
            WHERE invalid_at IS NULL AND tier = 'canonical'
              AND COALESCE(source_type, '') <> 'benchmark'
            """
        )
        canonical_ids = {str(r[0]) for r in cur.fetchall()}

        ledger_ids: set[str] = set()
        cur.execute("SELECT content FROM frank_ledger")
        for (content,) in cur.fetchall():
            try:
                payload = content if isinstance(content, dict) else json.loads(content)
            except (TypeError, ValueError):
                continue
            written = payload.get("atoms_written")
            if isinstance(written, list):
                ledger_ids.update(str(x) for x in written)

    total = len(canonical_ids)
    by_ledger = canonical_ids & ledger_ids
    supported = set(by_ledger)  # union of all *measured* support legs
    return {
        "report": "recon-canonical",
        "canonical_total": total,
        "supported": len(supported),
        "unsupported": total - len(supported),
        "by_support": {
            "ledger": len(by_ledger),
            "handoff": None,       # declared, not yet measured
            "source_trail": None,  # declared, not yet measured
        },
        "runs_present": True,
        "note": (
            "ledger-only support; handoff/source_trail legs unmeasured — "
            "reconstruction_cost is an upper bound"
        ),
    }


def stage_discernment(
    raw: dict[str, IngredientResult], config: dict[str, Any]
) -> dict[str, Any]:
    rr = raw.get("rendereason")
    metrics = config.get("discernment_metrics", [])
    structure = rr.structure if rr else {}
    atom_count = structure.get("rh_dirty_atom_count")
    signals = {
        "canon_promotion": atom_count is not None and atom_count > 0,
        "deprecated_suppression": _noise_suppression_signal(),
        "apo_vocab_preservation": any(
            "apo" in (h.get("title") or "").lower()
            or "apo" in (h.get("summary") or "").lower()
            for h in (rr.kb_hits if rr else [])
        ),
        "probe_top5_overlap": "requires_clean_dirty_compare",
    }
    return {
        "stage": "discernment",
        "metrics_requested": metrics,
        "rh_dirty_atom_count": atom_count,
        "harness_ready": structure.get("harness_exists", False),
        "signals": signals,
        "interpretation": (
            "Dirty corpus is indexed; full convergence needs "
            "`python3 -m sandbox.rh_harness.compare` after clean/dirty ingests."
        ),
    }


def stage_governance(raw: dict[str, IngredientResult]) -> dict[str, Any]:
    oak = raw.get("oakenscroll")
    gov = oak.governance if oak else {}
    scan = gov.get("persona_scan", {})
    passed = sum(1 for v in scan.values() if v)
    total = len(scan) or 1
    return {
        "stage": "governance",
        "checks": scan,
        "pass_ratio": round(passed / total, 2),
        "kb_hits": oak.kb_hits if oak else [],
        "verdict": (
            "frame_present"
            if passed >= total // 2 + 1
            else "frame_incomplete"
        ),
    }


def stage_synthesis(
    kb: dict[str, Any],
    prov: dict[str, Any],
    layers: dict[str, Any],
    disc: dict[str, Any],
    gov: dict[str, Any],
) -> dict[str, Any]:
    observations: list[str] = []
    tensions: list[str] = []
    follow_ups: list[str] = []

    for row in prov["classifications"]:
        if not row["has_kb_signal"]:
            tensions.append(f"No KB hits for `{row['id']}` — ingredient may be local-only.")

    if disc.get("rh_dirty_atom_count"):
        observations.append(
            f"Rendereason rh-dirty project has {disc['rh_dirty_atom_count']} live KB atoms."
        )
    else:
        tensions.append("rh-dirty atom count unavailable — Postgres or project empty.")

    rendereason_structure = kb.get("_structure_rendereason") or {}
    for name, meta in rendereason_structure.get("archives", {}).items():
        if meta.get("exists"):
            observations.append(
                f"Rendereason archive `{name}` present "
                f"({meta.get('members', 0)} members, "
                f"{len(meta.get('extensions', {}))} extension groups)."
            )

    angry = kb["ingredients"].get("angrybob", {})
    angrybob_structure = kb.get("_structure_angrybob") or {}
    for name, meta in angrybob_structure.get("local_dbs", {}).items():
        if meta.get("exists"):
            observations.append(
                f"angrybob `{name}` present ({meta.get('size_bytes', 0)} bytes, "
                f"{len(meta.get('tables', {}))} tables)."
            )
        else:
            follow_ups.append(f"Locate or restore `{name}` in fleet home.")
    for name, meta in angrybob_structure.get("archives", {}).items():
        if meta.get("exists"):
            observations.append(
                f"angrybob archive `{name}` present "
                f"({meta.get('members', 0)} members, "
                f"{len(meta.get('extensions', {}))} extension groups)."
            )
        else:
            follow_ups.append(f"Locate protected archive `{name}` in a configured private root.")

    paper_structure = kb.get("_structure_stone_soup_papers") or {}
    for name, meta in paper_structure.get("private_files", {}).items():
        if meta.get("exists"):
            concepts = ", ".join(f"`{c}`" for c in meta.get("concepts", [])[:6])
            observations.append(
                f"Stone Soup theory source `{name}` present "
                f"({meta.get('line_count', 0)} lines; concepts: {concepts})."
            )
            if meta.get("formal_labels"):
                observations.append(
                    "Formal labels extracted: "
                    + ", ".join(f"`{x}`" for x in meta["formal_labels"][:6])
                    + "."
                )
        else:
            follow_ups.append(f"Locate protected theory source `{name}`.")

    if gov.get("verdict") == "frame_present":
        observations.append(
            "Oakenscroll governance frame detected in persona overlay (posole / gaps / Dual Commit)."
        )

    layer_status = {layer["id"]: layer.get("status") for layer in layers.get("layers", [])}
    present_layers = [lid for lid, status in layer_status.items() if status == "present"]
    if present_layers:
        observations.append(
            "Willow layers in the pot: " + ", ".join(f"`{lid}`" for lid in present_layers) + "."
        )
    missing_layers = [lid for lid, status in layer_status.items() if status == "missing"]
    for lid in missing_layers:
        follow_ups.append(f"Layer `{lid}` reported missing; decide whether it belongs in this soup.")

    synthesis_layer = next(
        (layer for layer in layers.get("layers", []) if layer.get("id") == "existing_synthesis"),
        {},
    )
    anchors = synthesis_layer.get("signals", {}).get("anchors", [])
    if anchors:
        observations.append(
            "Existing synthesis anchors tied in: "
            + ", ".join(f"`{a.get('id')}`" for a in anchors[:4])
            + "."
        )

    candidate_atlas = []
    if disc.get("harness_ready") and disc.get("rh_dirty_atom_count"):
        candidate_atlas.append(
            "Extend rh_apo_discernment_harness with stone-soup staged report as optional sidecar."
        )

    return {
        "stage": "synthesis",
        "observations": observations,
        "tensions": tensions,
        "follow_ups": follow_ups,
        "candidate_atlas_entries": candidate_atlas,
        "promotion_recommendation": (
            "private_research_note"
            if tensions
            else "consider_sidecar_after_second_run"
        ),
    }


def render_markdown(stages: list[dict[str, Any]], *, generated_at: str) -> str:
    lines = [
        "# Stone Soup — Staged Dry Run",
        "",
        f"Generated: {generated_at}",
        "",
        "> Redacted report. No private corpus text. Summaries truncated.",
        "",
    ]

    for stage in stages:
        sid = stage["stage"]
        lines.append(f"## {sid.replace('_', ' ').title()}")
        lines.append("")

        if sid == "kb_retrieval":
            for iid, data in stage["ingredients"].items():
                lines.append(f"### {data['label']} (`{iid}`)")
                lines.append(f"- visibility: `{data['visibility']}`")
                lines.append(f"- hits: {data['hit_count']}")
                for hit in data["hits"]:
                    lines.append(
                        f"  - `{hit.get('id')}` — {hit.get('title')} "
                        f"({hit.get('project')}, {hit.get('tier')})"
                    )
                lines.append("")

        elif sid == "provenance":
            lines.append("| Ingredient | Visibility | KB signal | Local structure |")
            lines.append("| --- | --- | --- | --- |")
            for row in stage["classifications"]:
                lines.append(
                    f"| {row['id']} | {row['visibility']} | "
                    f"{'yes' if row['has_kb_signal'] else 'no'} | "
                    f"{'yes' if row['has_local_structure'] else 'no'} |"
                )
            lines.append("")

        elif sid == "willow_layers":
            lines.append("| Layer | Status | Question | Key signals |")
            lines.append("| --- | --- | --- | --- |")
            for layer in stage.get("layers", []):
                signals = layer.get("signals", {})
                signal_bits = []
                for key, value in signals.items():
                    if isinstance(value, (str, int, float)) or value is None:
                        signal_bits.append(f"{key}={value}")
                    elif isinstance(value, list):
                        signal_bits.append(f"{key}={len(value)}")
                    elif isinstance(value, dict):
                        signal_bits.append(f"{key}={len(value)}")
                lines.append(
                    f"| {layer.get('id')} | {layer.get('status')} | "
                    f"{layer.get('question', '')} | {'; '.join(signal_bits[:4])} |"
                )
            lines.append("")

        elif sid == "discernment":
            lines.append(f"- rh-dirty atoms: {stage.get('rh_dirty_atom_count')}")
            lines.append(f"- harness ready: {stage.get('harness_ready')}")
            lines.append("- signals:")
            for k, v in stage.get("signals", {}).items():
                lines.append(f"  - {k}: {v}")
            lines.append(f"- note: {stage.get('interpretation')}")
            lines.append("")

        elif sid == "governance":
            lines.append(f"- verdict: **{stage.get('verdict')}**")
            lines.append(f"- pass ratio: {stage.get('pass_ratio')}")
            lines.append("- checks:")
            for k, v in stage.get("checks", {}).items():
                lines.append(f"  - {k}: {'pass' if v else 'miss'}")
            lines.append("")

        elif sid == "alignment":
            lines.append(f"- **verdict:** `{stage.get('verdict')}`")
            lines.append(f"- **score:** {stage.get('score')}")
            lines.append("")
            lines.append("| Domain | Score | Passed |")
            lines.append("| --- | --- | --- |")
            for domain_id, meta in stage.get("domains", {}).items():
                lines.append(
                    f"| {meta.get('label', domain_id)} | {meta.get('score')} | "
                    f"{meta.get('passed')}/{meta.get('total')} |"
                )
            lines.append("")
            lines.append("| Metric | Invariant | Pass | Detail |")
            lines.append("| --- | --- | --- | --- |")
            for metric in stage.get("metrics", []):
                mark = "yes" if metric.get("passed") else "no"
                lines.append(
                    f"| {metric.get('id')} | {metric.get('invariant')} | {mark} | "
                    f"{metric.get('detail')} |"
                )
            failures = stage.get("failures", [])
            if failures:
                lines.append("")
                lines.append("**Failures:**")
                for fail in failures:
                    lines.append(
                        f"- `{fail.get('invariant')}` — {fail.get('label')}: {fail.get('detail')}"
                    )
            lines.append("")

        elif sid == "synthesis":
            for label, key in (
                ("Observations", "observations"),
                ("Tensions", "tensions"),
                ("Follow-ups", "follow_ups"),
                ("Candidate atlas", "candidate_atlas_entries"),
            ):
                items = stage.get(key, [])
                if items:
                    lines.append(f"**{label}:**")
                    for item in items:
                        lines.append(f"- {item}")
                    lines.append("")
            lines.append(
                f"**Promotion recommendation:** `{stage.get('promotion_recommendation')}`"
            )
            lines.append("")

        elif sid == "human_synthesis":
            lines.append(f"### {stage.get('headline')}")
            lines.append("")
            lines.append(
                f"- overall: **{stage.get('overall_verdict')}** "
                f"(score {stage.get('overall_score')})"
            )
            lines.append(f"- framing: {stage.get('framing')}")
            lines.append("")
            for label, key in (
                ("What aligns", "what_aligns"),
                ("Gaps", "gaps"),
                ("Next steps", "next_steps"),
            ):
                items = stage.get(key, [])
                if items:
                    lines.append(f"**{label}:**")
                    for item in items:
                        lines.append(f"- {item}")
                    lines.append("")

    lines.append("*ΔΣ=42*")
    return "\n".join(lines)


def run_pipeline(*, limit: int, app_id: str) -> tuple[list[dict[str, Any]], dict[str, IngredientResult]]:
    config = load_config()
    ingredients = config["ingredients"]

    kb_stage = stage_kb_retrieval(ingredients, limit=limit)
    raw: dict[str, IngredientResult] = kb_stage.pop("_raw")

    # Attach angrybob structure for synthesis without duplicating in markdown kb section
    ab = raw.get("angrybob")
    if ab:
        kb_stage["_structure_angrybob"] = {
            "local_dbs": ab.structure.get("local_dbs", {}),
            "archives": ab.structure.get("archives", {}),
        }
    rr = raw.get("rendereason")
    if rr:
        kb_stage["_structure_rendereason"] = {
            "archives": rr.structure.get("archives", {}),
        }
    soup_paper = raw.get("stone_soup_papers")
    if soup_paper:
        kb_stage["_structure_stone_soup_papers"] = {
            "private_files": soup_paper.structure.get("private_files", {}),
        }

    prov = stage_provenance(raw)
    # Refresh the W8 canonical-reconstruction census so the decoder_mismatch
    # metric reads a current saved report. Best-effort: DB down -> metric pending.
    try:
        recon = canonical_reconstruction_census(app_id=app_id)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / "recon-canonical.json").write_text(
            json.dumps(recon, indent=2), encoding="utf-8"
        )
    except Exception as exc:  # noqa: BLE001 — any failure leaves W8 pending
        print(f"[stone_soup] reconstruction census skipped: {exc}", file=sys.stderr)
    layers = collect_layers(config.get("willow_layers", []), limit=limit)
    disc = stage_discernment(raw, config)
    gov = stage_governance(raw)
    syn = stage_synthesis(kb_stage, prov, layers, disc, gov)
    alignment = evaluate_alignment(
        raw=raw, layers=layers, disc=disc, gov=gov, prov=prov
    )
    human = render_human_synthesis(alignment, syn)

    public_kb = {
        "stage": "kb_retrieval",
        "ingredients": kb_stage["ingredients"],
    }
    return [public_kb, prov, layers, disc, gov, alignment, syn, human], raw


def main() -> int:
    parser = argparse.ArgumentParser(description="Stone soup staged dry run")
    parser.add_argument("--limit", type=int, default=5, help="Max KB hits per ingredient")
    parser.add_argument("--app-id", default="willow", help="Willow MCP app_id")
    parser.add_argument(
        "--output",
        type=Path,
        default="",
        help="Markdown report path (default: reports/stone_soup-<ts>.md)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    args = parser.parse_args()

    # app_id reserved for future shim override
    _ = args.app_id

    stages, _raw = run_pipeline(limit=args.limit, app_id=args.app_id)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")

    if args.json:
        print(json.dumps({"generated_at": ts, "stages": stages}, indent=2))
        return 0

    md = render_markdown(stages, generated_at=ts)
    out = args.output or (REPORTS_DIR / f"stone_soup-{ts}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(md)
    print(f"\n[stone_soup] report written to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
