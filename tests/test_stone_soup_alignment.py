"""Tests for stone_soup alignment calculus (no live DB required)."""
from __future__ import annotations

from sandbox.stone_soup.adapters import IngredientResult
from sandbox.stone_soup.alignment import (
    evaluate_alignment,
    load_metrics_config,
    render_human_synthesis,
)


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
