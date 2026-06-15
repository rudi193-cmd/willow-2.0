"""Willow Alignment Calculus — measurable invariant checks (structure-only)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sandbox.stone_soup.adapters import IngredientResult
from sandbox.stone_soup.willow_shim import kb_search

METRICS_PATH = Path(__file__).resolve().parent / "alignment_metrics.json"

_HOME_PATH_RE = re.compile(r"(/home/[^\s]+|~[/\\][^\s]+)")


@dataclass
class MetricResult:
    id: str
    domain: str
    invariant: str
    label: str
    weight: float
    passed: bool
    detail: str
    signals: dict[str, Any] = field(default_factory=dict)


def load_metrics_config() -> dict[str, Any]:
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


def _layer_map(layers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {layer["id"]: layer for layer in layers.get("layers", [])}


def _layer_signal(layers: dict[str, Any], layer_id: str, field: str) -> Any:
    layer = _layer_map(layers).get(layer_id, {})
    return layer.get("signals", {}).get(field)


def _layer_status(layers: dict[str, Any], layer_id: str) -> str:
    return str(_layer_map(layers).get(layer_id, {}).get("status", "unknown"))


def _kb_text_blob(raw: dict[str, IngredientResult]) -> str:
    parts: list[str] = []
    for result in raw.values():
        for hit in result.kb_hits:
            parts.append(str(hit.get("title", "")))
            parts.append(str(hit.get("summary", "")))
    return " ".join(parts).lower()


def _archive_member_names(structure: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for meta in structure.get("archives", {}).values():
        if isinstance(meta, dict):
            names.extend(meta.get("member_names", []))
    return [n.lower() for n in names]


def _table_names(structure: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for db_entry in structure.get("local_dbs", {}).values():
        if isinstance(db_entry, dict):
            names.extend(db_entry.get("tables", {}).keys())
    return [n.lower() for n in names]


def _table_row_total(structure: dict[str, Any]) -> int:
    total = 0
    for db_entry in structure.get("local_dbs", {}).values():
        if not isinstance(db_entry, dict):
            continue
        for count in db_entry.get("tables", {}).values():
            if isinstance(count, int):
                total += count
    return total


def _archives_present(structure: dict[str, Any]) -> int:
    count = 0
    for meta in structure.get("archives", {}).values():
        if isinstance(meta, dict) and meta.get("exists"):
            count += 1
    return count


def _sources_present(structure: dict[str, Any]) -> bool:
    if _archives_present(structure) > 0:
        return True
    for db_entry in structure.get("local_dbs", {}).values():
        if isinstance(db_entry, dict) and db_entry.get("exists"):
            return True
    return False


def _concept_count(raw: dict[str, IngredientResult], ingredient_id: str) -> int:
    result = raw.get(ingredient_id)
    if not result:
        return 0
    total = 0
    for meta in result.structure.get("private_files", {}).values():
        if isinstance(meta, dict):
            total += len(meta.get("concepts", []))
    return total


@dataclass
class _MetricContext:
    """Shared inputs each metric evaluator may read."""

    metric: dict[str, Any]
    raw: dict[str, IngredientResult]
    layers: dict[str, Any]
    disc: dict[str, Any]
    gov: dict[str, Any]
    prov: dict[str, Any]
    rr_structure: dict[str, Any]
    ab_structure: dict[str, Any]
    kb_blob: str


# Each evaluator returns (passed, detail, signals).
_EvalResult = tuple[bool, str, dict[str, Any]]


def _eval_boolean_and(ctx: _MetricContext) -> _EvalResult:
    signals: dict[str, Any] = {}
    checks = []
    for signal in ctx.metric.get("signals", []):
        if signal == "rh_dirty_atom_count_gt_zero":
            val = ctx.rr_structure.get("rh_dirty_atom_count", 0) or 0
            checks.append(val > 0)
            signals[signal] = val
        elif signal == "harness_ready":
            val = bool(ctx.rr_structure.get("harness_exists"))
            checks.append(val)
            signals[signal] = val
    passed = all(checks) if checks else False
    return passed, f"checks={checks}", signals


def _eval_kb_keyword(ctx: _MetricContext) -> _EvalResult:
    metric = ctx.metric
    keywords = [k.lower() for k in metric.get("keywords", [])]
    ingredient_id = metric.get("ingredient", "")
    if ingredient_id and ingredient_id in ctx.raw:
        parts = []
        for hit in ctx.raw[ingredient_id].kb_hits:
            parts.append(str(hit.get("title", "")))
            parts.append(str(hit.get("summary", "")))
        blob = " ".join(parts).lower()
    else:
        blob = ctx.kb_blob
    hits = [k for k in keywords if k in blob]
    passed = len(hits) >= 1
    # Structural fallback: angrybob DB witness counts as cross-index
    if not passed and metric.get("structural_fallback") and ingredient_id == "angrybob":
        passed = _table_row_total(ctx.ab_structure) > 0
        signals = {
            "matched_keywords": hits,
            "scoped": ingredient_id,
            "structural_fallback": True,
            "db_rows": _table_row_total(ctx.ab_structure),
        }
        detail = f"structural fallback via {signals['db_rows']} DB rows"
    else:
        signals = {"matched_keywords": hits, "scoped": ingredient_id or "all"}
        detail = f"matched {len(hits)}/{len(keywords)} keywords"
    return passed, detail, signals


def _eval_archive_present(ctx: _MetricContext) -> _EvalResult:
    count = _archives_present(ctx.rr_structure)
    min_archives = int(ctx.metric.get("min_archives", 1))
    passed = count >= min_archives
    return passed, f"{count} archive(s) present (need {min_archives})", {"archives_present": count}


def _eval_probe_diversity(ctx: _MetricContext) -> _EvalResult:
    titles: set[str] = set()
    for query in ctx.metric.get("queries", []):
        for hit in kb_search(query, limit=3, project="rh-dirty"):
            title = hit.get("title")
            if title:
                titles.add(title)
    min_unique = int(ctx.metric.get("min_unique_titles", 2))
    passed = len(titles) >= min_unique
    signals = {"unique_titles": len(titles), "sample": sorted(titles)[:4]}
    return passed, f"{len(titles)} unique probe titles (need {min_unique})", signals


def _eval_discernment_flag(ctx: _MetricContext) -> _EvalResult:
    flag = ctx.metric.get("flag", "")
    val = ctx.disc.get("signals", {}).get(flag)
    passed = val not in (False, None, "")
    return passed, f"{flag}={val!r}", {flag: val}


def _eval_rh_noise_probe(ctx: _MetricContext) -> _EvalResult:
    query = ctx.metric.get(
        "query",
        "deprecated failed iteration non-canon discard",
    )
    hits = kb_search(query, limit=5, project="rh-dirty")
    top_titles = [(h.get("title") or "") for h in hits[:3]]
    noise_in_top3 = [
        t for t in top_titles if "deprecated" in t.lower() or "[dirty] deprecated" in t.lower()
    ]
    passed = len(noise_in_top3) == 0 and len(hits) > 0
    signals = {"top_titles": top_titles, "noise_in_top3": noise_in_top3}
    detail = "no deprecated in top-3" if passed else f"noise surfaced: {noise_in_top3!r}"
    return passed, detail, signals


def _eval_source_present(ctx: _MetricContext) -> _EvalResult:
    passed = _sources_present(ctx.ab_structure)
    signals = {
        "archives": _archives_present(ctx.ab_structure),
        "dbs": sum(
            1
            for e in ctx.ab_structure.get("local_dbs", {}).values()
            if isinstance(e, dict) and e.get("exists")
        ),
    }
    detail = "archive or DB present" if passed else "no angrybob source found"
    return passed, detail, signals


def _eval_table_pattern(ctx: _MetricContext) -> _EvalResult:
    patterns = [p.lower() for p in ctx.metric.get("patterns", [])]
    names = _table_names(ctx.ab_structure)
    archive_names = _archive_member_names(ctx.ab_structure)
    combined = names + archive_names
    matched = [n for n in combined if any(p in n for p in patterns)]
    passed = len(matched) >= 1
    signals = {
        "matched_tables": matched[:8],
        "all_tables": names[:12],
        "archive_members": archive_names[:12],
    }
    return passed, f"matched {len(matched)} name(s) for patterns {patterns}", signals


def _eval_table_row_count(ctx: _MetricContext) -> _EvalResult:
    total = _table_row_total(ctx.ab_structure)
    min_rows = int(ctx.metric.get("min_rows", 1))
    # Archive with DB members counts as non-empty rule store (structure signal)
    archive_has_db = any(
        name.endswith(".db")
        for name in _archive_member_names(ctx.ab_structure)
    )
    passed = total >= min_rows or archive_has_db
    signals = {"total_rows": total, "archive_has_db": archive_has_db}
    detail = f"total rows={total}, archive_has_db={archive_has_db} (need rows≥{min_rows} or db member)"
    return passed, detail, signals


def _eval_layer_signal(ctx: _MetricContext) -> _EvalResult:
    layer_id = ctx.metric.get("layer", "")
    field_name = ctx.metric.get("field", "")
    min_value = int(ctx.metric.get("min_value", 1))
    value = _layer_signal(ctx.layers, layer_id, field_name)
    numeric = int(value) if isinstance(value, (int, float)) else 0
    passed = numeric >= min_value
    return passed, f"{layer_id}.{field_name}={value!r} (need ≥{min_value})", {field_name: value}


def _eval_layer_status(ctx: _MetricContext) -> _EvalResult:
    layer_id = ctx.metric.get("layer", "")
    required = ctx.metric.get("required_status", "present")
    status = _layer_status(ctx.layers, layer_id)
    passed = status == required
    return passed, f"{layer_id} status={status!r} (need {required!r})", {"status": status}


def _eval_governance_verdict(ctx: _MetricContext) -> _EvalResult:
    required = ctx.metric.get("required_verdict", "frame_present")
    verdict = ctx.gov.get("verdict", "")
    passed = verdict == required
    return passed, f"verdict={verdict!r}", {"verdict": verdict, "pass_ratio": ctx.gov.get("pass_ratio")}


def _eval_layer_coverage(ctx: _MetricContext) -> _EvalResult:
    layer_rows = ctx.layers.get("layers", [])
    total = len(layer_rows) or 1
    present = sum(1 for layer in layer_rows if layer.get("status") == "present")
    ratio = present / total
    min_ratio = float(ctx.metric.get("min_ratio", 0.7))
    passed = ratio >= min_ratio
    signals = {"present": present, "total": total, "ratio": round(ratio, 3)}
    return passed, f"coverage {present}/{total} ({ratio:.0%})", signals


def _eval_concept_count(ctx: _MetricContext) -> _EvalResult:
    ingredient_id = ctx.metric.get("ingredient", "")
    count = _concept_count(ctx.raw, ingredient_id)
    min_concepts = int(ctx.metric.get("min_concepts", 1))
    passed = count >= min_concepts
    return passed, f"{count} concepts (need {min_concepts})", {"concept_count": count}


def _eval_provenance_complete(ctx: _MetricContext) -> _EvalResult:
    rows = ctx.prov.get("classifications", [])
    passed = all(
        row.get("has_kb_signal") or row.get("has_local_structure")
        for row in rows
    )
    complete = sum(
        1
        for row in rows
        if row.get("has_kb_signal") or row.get("has_local_structure")
    )
    signals = {"ingredients": len(rows), "complete": complete}
    return passed, f"{complete}/{len(rows)} ingredients witnessed", signals


def _eval_redaction_check(ctx: _MetricContext) -> _EvalResult:
    # Scan layer/handoff signals for absolute home paths in values we emit
    leaks: list[str] = []
    handoff_root = _layer_signal(ctx.layers, "handoff", "handoff_root")
    if isinstance(handoff_root, str) and _HOME_PATH_RE.search(handoff_root):
        leaks.append("handoff_root")
    passed = len(leaks) == 0
    detail = "no absolute path leaks" if passed else f"leaks: {leaks}"
    return passed, detail, {"leaks": leaks}


_METRIC_EVALUATORS: dict[str, Any] = {
    "boolean_and": _eval_boolean_and,
    "kb_keyword": _eval_kb_keyword,
    "archive_present": _eval_archive_present,
    "probe_diversity": _eval_probe_diversity,
    "discernment_flag": _eval_discernment_flag,
    "rh_noise_probe": _eval_rh_noise_probe,
    "source_present": _eval_source_present,
    "table_pattern": _eval_table_pattern,
    "table_row_count": _eval_table_row_count,
    "layer_signal": _eval_layer_signal,
    "layer_status": _eval_layer_status,
    "governance_verdict": _eval_governance_verdict,
    "layer_coverage": _eval_layer_coverage,
    "concept_count": _eval_concept_count,
    "provenance_complete": _eval_provenance_complete,
    "redaction_check": _eval_redaction_check,
}


def _evaluate_metric(
    metric: dict[str, Any],
    *,
    raw: dict[str, IngredientResult],
    layers: dict[str, Any],
    disc: dict[str, Any],
    gov: dict[str, Any],
    prov: dict[str, Any],
) -> MetricResult:
    rr = raw.get("rendereason")
    ab = raw.get("angrybob")
    ctx = _MetricContext(
        metric=metric,
        raw=raw,
        layers=layers,
        disc=disc,
        gov=gov,
        prov=prov,
        rr_structure=rr.structure if rr else {},
        ab_structure=ab.structure if ab else {},
        kb_blob=_kb_text_blob(raw),
    )

    evaluator = _METRIC_EVALUATORS.get(metric.get("kind", ""))
    if evaluator is None:
        passed, detail, signals = False, "unimplemented", {}
    else:
        passed, detail, signals = evaluator(ctx)

    return MetricResult(
        id=metric["id"],
        domain=metric.get("domain", ""),
        invariant=metric.get("invariant", ""),
        label=metric.get("label", metric["id"]),
        weight=float(metric.get("weight", 1.0)),
        passed=passed,
        detail=detail,
        signals=signals,
    )


# Projection maps Φ (alignment_calculus.md §5) — which map carries each
# domain's invariants into the shared claim/process graph 𝒢.
_PROJECTION = {
    "rendereason": "Φ_render",
    "angrybob": "Φ_bob",
    "willow": "Φ_willow",
    "cross": "Φ_soup",
}


@dataclass
class InvariantWitness:
    """One metric reframed as evidence for an invariant predicate I ∈ 𝓘.

    The alignment calculus (alignment_calculus.md §1) measures alignment as
    I(v) ⇒ I(π(v)): an invariant that holds in a source domain must survive
    its projection π into the shared graph 𝒢. Each metric is the measurable
    proxy for one such invariant; an InvariantWitness records whether that
    invariant was *witnessed* under its projection Φ, plus the evidence that
    did the witnessing. Score is unaffected — this is the structured view of
    the same pass/fail the metric already produced.
    """

    invariant: str           # R1..R5 | B1..B5 | W1..W7 | X1..X3
    domain: str              # rendereason | angrybob | willow | cross
    projection: str          # Φ map carrying the invariant into 𝒢
    label: str
    weight: float
    witnessed: bool          # invariant holds under projection (== metric passed)
    proxy: str               # how it was measured (metric detail)
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return "witnessed" if self.witnessed else "absent"

    def as_dict(self) -> dict[str, Any]:
        return {
            "invariant": self.invariant,
            "domain": self.domain,
            "projection": self.projection,
            "label": self.label,
            "weight": self.weight,
            "witnessed": self.witnessed,
            "status": self.status,
            "proxy": self.proxy,
            "evidence": self.evidence,
        }


def _witness_from_metric(result: MetricResult) -> InvariantWitness:
    return InvariantWitness(
        invariant=result.invariant or result.id,
        domain=result.domain,
        projection=_PROJECTION.get(result.domain, "Φ_soup"),
        label=result.label,
        weight=result.weight,
        witnessed=result.passed,
        proxy=result.detail,
        evidence=result.signals,
    )


def _witness_summary(witnesses: list[InvariantWitness]) -> dict[str, Any]:
    """Aggregate witnesses by projection Φ — weight-coverage per map."""
    by_proj: dict[str, dict[str, Any]] = {}
    for w in witnesses:
        slot = by_proj.setdefault(
            w.projection,
            {
                "witnessed": 0,
                "absent": 0,
                "total": 0,
                "weight_witnessed": 0.0,
                "weight_total": 0.0,
            },
        )
        slot["total"] += 1
        slot["weight_total"] += w.weight
        if w.witnessed:
            slot["witnessed"] += 1
            slot["weight_witnessed"] += w.weight
        else:
            slot["absent"] += 1
    for slot in by_proj.values():
        wt = slot["weight_total"] or 1.0
        slot["coverage"] = round(slot["weight_witnessed"] / wt, 3)
        slot["weight_witnessed"] = round(slot["weight_witnessed"], 3)
        slot["weight_total"] = round(slot["weight_total"], 3)
    return by_proj


def evaluate_alignment(
    *,
    raw: dict[str, IngredientResult],
    layers: dict[str, Any],
    disc: dict[str, Any],
    gov: dict[str, Any],
    prov: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate all alignment metrics and return scored summary."""
    cfg = config or load_metrics_config()
    metrics_cfg = cfg.get("metrics", [])
    results: list[MetricResult] = []

    for metric in metrics_cfg:
        results.append(
            _evaluate_metric(
                metric,
                raw=raw,
                layers=layers,
                disc=disc,
                gov=gov,
                prov=prov,
            )
        )

    total_weight = sum(r.weight for r in results) or 1.0
    passed_weight = sum(r.weight for r in results if r.passed)
    score = round(passed_weight / total_weight, 3)

    bands = cfg.get("verdict_bands", {})
    aligned_min = float(bands.get("aligned", 0.75))
    partial_min = float(bands.get("partial", 0.45))
    if score >= aligned_min:
        verdict = "aligned"
    elif score >= partial_min:
        verdict = "partial"
    else:
        verdict = "misaligned"

    by_domain: dict[str, dict[str, Any]] = {}
    for domain_id, meta in cfg.get("domains", {}).items():
        domain_results = [r for r in results if r.domain == domain_id]
        d_weight = sum(r.weight for r in domain_results) or 1.0
        d_passed = sum(r.weight for r in domain_results if r.passed)
        by_domain[domain_id] = {
            "label": meta.get("label", domain_id),
            "invariants": meta.get("invariants", []),
            "score": round(d_passed / d_weight, 3),
            "passed": sum(1 for r in domain_results if r.passed),
            "total": len(domain_results),
        }

    failures = [
        {"id": r.id, "invariant": r.invariant, "label": r.label, "detail": r.detail}
        for r in results
        if not r.passed
    ]

    witnesses = [_witness_from_metric(r) for r in results]

    return {
        "stage": "alignment",
        "score": score,
        "verdict": verdict,
        "verdict_bands": bands,
        "domains": by_domain,
        "metrics": [
            {
                "id": r.id,
                "domain": r.domain,
                "invariant": r.invariant,
                "label": r.label,
                "weight": r.weight,
                "passed": r.passed,
                "detail": r.detail,
                "signals": r.signals,
            }
            for r in results
        ],
        "failures": failures,
        "witnesses": [w.as_dict() for w in witnesses],
        "witness_summary": _witness_summary(witnesses),
    }


def render_human_synthesis(alignment: dict[str, Any], syn: dict[str, Any]) -> dict[str, Any]:
    """Human-facing synthesis from alignment metrics + stone-soup observations."""
    score = alignment.get("score", 0)
    verdict = alignment.get("verdict", "unknown")
    domains = alignment.get("domains", {})
    failures = alignment.get("failures", [])

    what_lines: list[str] = []
    gap_lines: list[str] = []
    next_lines: list[str] = []

    for domain_id, meta in domains.items():
        label = meta.get("label", domain_id)
        d_score = meta.get("score", 0)
        passed = meta.get("passed", 0)
        total = meta.get("total", 0)
        if d_score >= 0.75:
            what_lines.append(
                f"**{label}** ({domain_id}): strong alignment ({passed}/{total} metrics, score {d_score:.0%})."
            )
        elif d_score >= 0.45:
            what_lines.append(
                f"**{label}** ({domain_id}): partial alignment ({passed}/{total} metrics, score {d_score:.0%})."
            )
        else:
            gap_lines.append(
                f"**{label}** ({domain_id}): weak alignment ({passed}/{total} metrics, score {d_score:.0%})."
            )

    for obs in syn.get("observations", [])[:6]:
        what_lines.append(obs)

    for fail in failures[:8]:
        gap_lines.append(f"`{fail['invariant']}` ({fail['id']}): {fail['detail']}")

    for item in syn.get("follow_ups", [])[:4]:
        next_lines.append(item)

    if verdict == "aligned":
        headline = (
            "Willow preserves most shared invariants across Rendereason, angrybob, "
            "and its own reconstruction layers."
        )
    elif verdict == "partial":
        headline = (
            "Willow lines up structurally with both projects, but full mathematical "
            "alignment still needs compare runs and deeper admissibility wiring."
        )
    else:
        headline = (
            "Willow is not yet aligned — missing sources or layer witnesses dominate."
        )

    if disc_note := _cross_domain_reading(alignment):
        what_lines.append(disc_note)

    next_lines.extend(
        [
            "Run `python3 -m sandbox.rh_harness.compare` for R1/R3 clean-dirty convergence.",
            "Re-run alignment after any angrybob DB extract or rh-dirty ingest.",
        ]
    )

    return {
        "stage": "human_synthesis",
        "headline": headline,
        "overall_verdict": verdict,
        "overall_score": score,
        "what_aligns": what_lines,
        "gaps": gap_lines,
        "next_steps": next_lines,
        "framing": (
            "Alignment is invariant preservation under projection, not fluent commentary. "
            "See alignment_calculus.md for objects, maps, and failure modes."
        ),
    }


def _cross_domain_reading(alignment: dict[str, Any]) -> str:
    render = alignment.get("domains", {}).get("rendereason", {})
    bob = alignment.get("domains", {}).get("angrybob", {})
    willow = alignment.get("domains", {}).get("willow", {})
    cross = alignment.get("domains", {}).get("cross", {})

    parts = []
    if render.get("score", 0) >= 0.5 and bob.get("score", 0) >= 0.5:
        parts.append(
            "Rendereason (canon under noise) and angrybob (admissible moves) both "
            "project into Willow's claim/process graph."
        )
    if willow.get("score", 0) >= 0.7:
        parts.append(
            "Willow's provenance, Jeles, ledger, and handoff layers witness "
            "reconstruction machinery for decoder mismatch."
        )
    if cross.get("score", 0) >= 0.7:
        parts.append(
            "Stone Soup theory concepts bridge the pot: recipe ≠ grandmother, "
            "alignment = measured invariant preservation."
        )
    return " ".join(parts)
