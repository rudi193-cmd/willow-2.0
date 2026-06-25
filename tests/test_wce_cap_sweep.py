"""Unit tests for WCE cap-sweep variant builder and knee picker."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from willow.bench.continuity.run_wce import (  # noqa: E402
    build_weight_variants,
    pick_knee_cap,
    _parse_float_list,
)


def test_parse_float_list():
    assert _parse_float_list("1.0, 1.3,1.5") == [1.0, 1.3, 1.5]
    assert _parse_float_list("") == []


def test_cap_sweep_builds_labeled_variants():
    variants = build_weight_variants(
        ablate=False,
        weight_mode="log",
        cap_sweep=[1.3, 1.5],
        weight_cap=2.0,
        cosine_bypass=0.55,
    )
    labels = [v.label for v in variants]
    assert labels == ["log", "off", "cap@1.3", "cap@1.5"]
    cap13 = next(v for v in variants if v.label == "cap@1.3")
    assert cap13.weight_mode == "cap"
    assert cap13.weight_cap == 1.3


def test_pick_knee_cap_respects_warm_floor():
    by_mode = {
        "log": {"cold_relevant_recall": 0.15, "warm_relevant_recall": 0.50},
        "off": {"cold_relevant_recall": 0.21, "warm_relevant_recall": 0.36},
        "cap@1.0": {"cold_relevant_recall": 0.18, "warm_relevant_recall": 0.49},
        "cap@1.5": {"cold_relevant_recall": 0.17, "warm_relevant_recall": 0.51},
        "cap@2.0": {"cold_relevant_recall": 0.15, "warm_relevant_recall": 0.50},
    }
    knee = pick_knee_cap(by_mode, baseline="log", warm_tolerance=0.035)
    assert knee["knee"] == "cap@1.0"
    assert knee["weight_cap"] == 1.0
    assert knee["cold_relevant_recall"] == 0.18


def test_pick_knee_cap_none_when_all_cap_rows_cold_on_warm():
    by_mode = {
        "log": {"cold_relevant_recall": 0.15, "warm_relevant_recall": 0.50},
        "cap@1.0": {"cold_relevant_recall": 0.20, "warm_relevant_recall": 0.40},
    }
    knee = pick_knee_cap(by_mode, baseline="log", warm_tolerance=0.02)
    assert knee["knee"] is None
