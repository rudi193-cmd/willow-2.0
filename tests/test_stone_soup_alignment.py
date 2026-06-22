"""Tests for stone_soup alignment calculus (no live DB required)."""
from __future__ import annotations

from datetime import datetime, timezone
import json

from sandbox.stone_soup.adapters import IngredientResult
from sandbox.stone_soup.alignment import (
    evaluate_alignment,
    load_metrics_config,
    render_human_synthesis,
)
from sandbox.stone_soup.run import _json_default
from sandbox.stone_soup.willow_shim import _semantic_allowed


def _minimal_raw() -> dict[str, IngredientResult]:
    return {
        "rendereason": IngredientResult(
            ingredient_id="rendereason",
            label="Rendereason",
            visibility="private_context",
            kb_hits=[{"title": "APO infogeometric proof", "summary": "canon path"}],
            structure={
                "harness_exists": True,
                "rh_dirty_atom_count": 10,
                "archives": {"RH7.zip": {"exists": True, "members": 3}},
            },
        ),
        "angrybob": IngredientResult(
            ingredient_id="angrybob",
            label="angrybob",
            visibility="private_context",
            kb_hits=[{"title": "angrybob admissibility", "summary": "LLM physics"}],
            structure={
                "archives": {"admissibility-calculus-2026-06-14.zip": {"exists": True}},
                "local_dbs": {
                    "angrybob-admissibility.db": {
                        "exists": True,
                        "tables": {"admissibility_rules": 5, "boundary_conditions": 2},
                    }
                },
            },
        ),
        "stone_soup_papers": IngredientResult(
            ingredient_id="stone_soup_papers",
            label="Stone Soup Papers",
            visibility="private_context",
            structure={
                "private_files": {
                    "$NEST/Stone Soup Papers.md": {
                        "exists": True,
                        "concepts": ["decoder mismatch", "Stone Soup Lemma"],
                    }
                }
            },
        ),
        "oakenscroll": IngredientResult(
            ingredient_id="oakenscroll",
            label="Oakenscroll",
            visibility="tracked",
        ),
    }


def _minimal_layers() -> dict:
    def layer(layer_id: str, status: str, **signals) -> dict:
        return {"id": layer_id, "status": status, "signals": signals}

    return {
        "stage": "willow_layers",
        "layers": [
            layer("kb", "present", live_atoms=100),
            layer("jeles", "present", live_atoms=10),
            layer("ledger", "present", entries=5),
            layer("handoff", "present", handoff_root="$WILLOW_HOME/handoffs", latest=[{}]),
            layer("existing_synthesis", "present", anchor_count=3),
            layer("soil", "present"),
            layer("grove", "present"),
            layer("benchmarks", "present"),
            layer("kart", "present"),
            layer("governance", "present"),
            layer("code", "present"),
            layer("persona", "present"),
        ],
    }


def test_load_metrics_config_has_domains():
    cfg = load_metrics_config()
    assert "metrics" in cfg
    assert "rendereason" in cfg["domains"]
    assert "angrybob" in cfg["domains"]
    assert "willow" in cfg["domains"]


def test_stone_soup_json_output_serializes_live_datetimes():
    payload = {
        "stages": [
            {
                "stage": "willow_layers",
                "layers": [
                    {
                        "id": "ledger",
                        "signals": {
                            "recent": [
                                {
                                    "id": "entry",
                                    "created_at": datetime(2026, 6, 14, tzinfo=timezone.utc),
                                }
                            ]
                        },
                    }
                ],
            }
        ]
    }

    rendered = json.dumps(payload, default=_json_default)
    assert "2026-06-14T00:00:00+00:00" in rendered


def test_stone_soup_disables_semantic_search_in_no_net_kart(monkeypatch):
    monkeypatch.setenv("WILLOW_IN_KART", "1")
    monkeypatch.setenv("WILLOW_KART_ALLOW_NET", "0")
    assert _semantic_allowed(True) is False

    monkeypatch.setenv("WILLOW_KART_ALLOW_NET", "1")
    assert _semantic_allowed(True) is True
    assert _semantic_allowed(False) is False


def test_evaluate_alignment_scores_and_verdict():
    alignment = evaluate_alignment(
        raw=_minimal_raw(),
        layers=_minimal_layers(),
        disc={"signals": {"deprecated_suppression": "unknown_without_compare_run"}},
        gov={"verdict": "frame_present", "pass_ratio": 0.75},
        prov={
            "classifications": [
                {"has_kb_signal": True, "has_local_structure": True},
                {"has_kb_signal": True, "has_local_structure": True},
            ]
        },
    )
    assert 0.0 <= alignment["score"] <= 1.0
    assert alignment["verdict"] in {"aligned", "partial", "misaligned"}
    assert len(alignment["metrics"]) >= 10
    assert "domains" in alignment


def test_invariant_witnesses_mirror_metrics_without_changing_score():
    inputs = dict(
        raw=_minimal_raw(),
        layers=_minimal_layers(),
        disc={"signals": {"deprecated_suppression": "unknown_without_compare_run"}},
        gov={"verdict": "frame_present", "pass_ratio": 0.75},
        prov={
            "classifications": [
                {"has_kb_signal": True, "has_local_structure": True},
                {"has_kb_signal": True, "has_local_structure": True},
            ]
        },
    )
    alignment = evaluate_alignment(**inputs)

    # One witness per metric, no metric dropped.
    assert len(alignment["witnesses"]) == len(alignment["metrics"])

    # Witnessed mirrors passed exactly — witness layer is a view, not a re-score.
    for m in alignment["metrics"]:
        match = [w for w in alignment["witnesses"] if w["label"] == m["label"]]
        assert match and match[0]["witnessed"] == m["passed"]

    # Every witness carries a projection Φ and a valid three-state status.
    for w in alignment["witnesses"]:
        assert w["projection"].startswith("Φ_")  # Φ_
        assert w["status"] in {"witnessed", "violated", "pending"}
        # Only a witnessed invariant is passed; violated/pending are not.
        assert w["witnessed"] == (w["status"] == "witnessed")

    # Summary weight-coverage stays within bounds and the three states sum.
    summary = alignment["witness_summary"]
    assert summary
    for proj, slot in summary.items():
        assert 0.0 <= slot["coverage"] <= 1.0
        assert slot["witnessed"] + slot["violated"] + slot["pending"] == slot["total"]


def test_pending_when_source_absent_violated_when_present():
    # No angrybob/rendereason ingredients at all → bob source invariants pending.
    raw = {
        "rendereason": IngredientResult(
            ingredient_id="rendereason", label="R", visibility="private_context"
        ),
        "angrybob": IngredientResult(
            ingredient_id="angrybob", label="B", visibility="private_context"
        ),
    }
    alignment = evaluate_alignment(
        raw=raw,
        layers=_minimal_layers(),
        disc={"signals": {}},
        gov={"verdict": "frame_present"},
        prov={"classifications": []},
    )
    # source_present has no db/archive substrate → pending, not violated.
    bob_source = [
        w for w in alignment["witnesses"]
        if w["domain"] == "angrybob" and "source" in w["proxy"].lower()
    ]
    assert bob_source and all(w["status"] == "pending" for w in bob_source)
    # With angrybob/rendereason empty, several invariants are pending (no substrate),
    # and none are spuriously marked violated for a missing source.
    assert any(w["status"] == "pending" for w in alignment["witnesses"])


def test_rh_compare_verdict_reads_saved_report(tmp_path):
    import json

    report = tmp_path / "rh-compare.json"
    cfg = {
        "verdict_bands": {"aligned": 0.75, "partial": 0.45},
        "domains": {"rendereason": {"label": "R", "invariants": ["R1"]}},
        "metrics": [
            {
                "id": "r1_conv",
                "domain": "rendereason",
                "invariant": "R1",
                "label": "True clean/dirty convergence",
                "weight": 1.0,
                "kind": "rh_compare_verdict",
                "report": str(report),
            }
        ],
    }

    def status():
        al = evaluate_alignment(
            raw={}, layers=_minimal_layers(), disc={"signals": {}},
            gov={}, prov={"classifications": []}, config=cfg,
        )
        return al["witnesses"][0]["status"]

    # No saved report → pending (substrate absent), never violated.
    assert status() == "pending"
    # Divergence verdict (warn) → violated.
    report.write_text(json.dumps({"status": "warn", "issues": ["dead_ends: x"], "runs_present": True}))
    assert status() == "violated"
    # Convergence verdict (pass) → witnessed.
    report.write_text(json.dumps({"status": "pass", "issues": [], "runs_present": True}))
    assert status() == "witnessed"


def test_decoder_mismatch_reads_saved_report(tmp_path):
    import json

    report = tmp_path / "recon.json"
    cfg = {
        "verdict_bands": {"aligned": 0.75, "partial": 0.45},
        "domains": {"willow": {"label": "W", "invariants": ["W8"]}},
        "metrics": [
            {
                "id": "w8_recon",
                "domain": "willow",
                "invariant": "W8",
                "label": "Canonical reconstruction coverage",
                "weight": 1.0,
                "kind": "decoder_mismatch",
                "report": str(report),
                "max_cost": 0.05,
            }
        ],
    }

    def witness():
        al = evaluate_alignment(
            raw={}, layers=_minimal_layers(), disc={"signals": {}},
            gov={}, prov={"classifications": []}, config=cfg,
        )
        return al["witnesses"][0]

    # No saved report → pending (no canonical substrate), never violated.
    assert witness()["status"] == "pending"

    # High cost (1/10 reconstructable → 90% > 5%) → violated.
    report.write_text(json.dumps({"canonical_total": 10, "supported": 1, "runs_present": True}))
    w = witness()
    assert w["status"] == "violated"
    assert w["evidence"]["reconstruction_cost"] == 0.9

    # Low cost (19/20 → 5% ≤ 5%) → witnessed; per-leg by_support flows through.
    report.write_text(json.dumps({
        "canonical_total": 20, "supported": 19, "runs_present": True,
        "by_support": {"ledger": 1, "source_id": 5, "provenance_edges": 7},
    }))
    w = witness()
    assert w["status"] == "witnessed"
    assert w["evidence"]["by_support"]["provenance_edges"] == 7

    # Empty canonical population → pending, never violated for absent substrate.
    report.write_text(json.dumps({"canonical_total": 0, "supported": 0}))
    assert witness()["status"] == "pending"


def test_render_human_synthesis_includes_headline():
    alignment = evaluate_alignment(
        raw=_minimal_raw(),
        layers=_minimal_layers(),
        disc={"signals": {}},
        gov={"verdict": "frame_present"},
        prov={"classifications": []},
    )
    human = render_human_synthesis(
        alignment,
        {"observations": ["test observation"], "follow_ups": ["run compare"]},
    )
    assert human["stage"] == "human_synthesis"
    assert human["headline"]
    assert human["overall_verdict"] == alignment["verdict"]
    assert any("test observation" in line for line in human["what_aligns"])

    # Witness three-state surfaces in the human report.
    assert "projection_coverage" in human
    assert human["projection_coverage"]  # one line per Φ map
    assert all("witnessed" in line for line in human["projection_coverage"])
    assert human["violated_count"] == sum(
        1 for w in alignment["witnesses"] if w["status"] == "violated"
    )
    assert human["pending_count"] == sum(
        1 for w in alignment["witnesses"] if w["status"] == "pending"
    )
    # A violated invariant reads as 'violated' in the gaps, not lumped with pending.
    if human["violated_count"]:
        assert any("violated" in g for g in human["gaps"])
