"""Unit tests for WCE memory-layer ablation (B0-B3) helpers."""
from __future__ import annotations

from willow.bench.continuity.run_wce import (
    aggregate_layers,
    build_memory_layers,
)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        pass

    def fetchall(self):
        return self._rows


class _FakePg:
    """Minimal PgBridge stand-in for build_memory_layers."""

    def __init__(self, source_types):
        self._rows = [(s,) for s in source_types]

    def _ensure_conn(self):
        pass

    @property
    def conn(self):
        return self

    def cursor(self, *a, **k):
        return _FakeCursor(self._rows)


def test_layers_are_cumulative_and_ordered():
    pg = _FakePg(["session", "mcp", "external", "benchmark", "weird_new_type"])
    layers = build_memory_layers(pg)
    labels = [label for label, _ in layers]
    assert labels == ["B0_handoff", "B1_kb", "B2_external", "B3_full"]
    sets = [set(stypes) for _, stypes in layers]
    # Each layer is a superset of the previous (cumulative).
    for prev, cur in zip(sets, sets[1:]):
        assert prev <= cur


def test_full_excludes_benchmark_includes_unknown():
    pg = _FakePg(["session", "mcp", "benchmark", "weird_new_type"])
    layers = dict(build_memory_layers(pg))
    full = set(layers["B3_full"])
    assert "benchmark" not in full          # LoCoMo contamination excluded
    assert "weird_new_type" in full         # any non-excluded embedded type included
    assert "session" in full and "mcp" in full


def test_handoff_layer_is_session_family():
    pg = _FakePg(["session"])
    b0 = dict(build_memory_layers(pg))["B0_handoff"]
    assert "session" in b0 and "session_promote" in b0 and "hook_stop" in b0


def _result(cold_by_layer, *, n_cold=4, cold_by_source=None):
    return {
        "id": "q",
        "n_cold_relevant": n_cold,
        "cold_by_source": cold_by_source or {},
        "layers": {
            label: {
                "cold_relevant_recall": c,
                "warm_relevant_recall": 0.5,
                "relevant_recall": 0.4,
            }
            for label, c in cold_by_layer.items()
        },
    }


def test_aggregate_marginal_lift_and_source_mix():
    labels = ["B0_handoff", "B1_kb", "B2_external", "B3_full"]
    results = [
        _result(
            {"B0_handoff": 0.1, "B1_kb": 0.2, "B2_external": 0.2, "B3_full": 0.15},
            cold_by_source={"session_promote": 3, "mcp": 1},
        ),
        _result(
            {"B0_handoff": 0.2, "B1_kb": 0.4, "B2_external": 0.4, "B3_full": 0.35},
            cold_by_source={"mcp": 2},
        ),
    ]
    agg = aggregate_layers(results, labels)
    assert agg["queries_scored"] == 2
    # Means: B0=0.15, B1=0.30, B2=0.30, B3=0.25
    assert agg["by_layer"]["B0_handoff"]["cold_relevant_recall"] == 0.15
    assert agg["by_layer"]["B1_kb"]["cold_relevant_recall"] == 0.30
    marg = agg["marginal_cold_lift"]
    assert marg["B0_handoff->B1_kb"] == 0.15
    assert marg["B1_kb->B2_external"] == 0.0
    assert marg["B2_external->B3_full"] == -0.05   # full-stack regression captured
    # Source mix aggregates across queries, sorted desc.
    dist = agg["cold_source_distribution"]
    assert dist["mcp"] == 3 and dist["session_promote"] == 3
    assert list(dist.keys())[0] in ("mcp", "session_promote")


def test_aggregate_skips_queries_without_cold_relevant():
    labels = ["B0_handoff", "B1_kb", "B2_external", "B3_full"]
    results = [
        _result({label: 0.0 for label in labels}, n_cold=0),
    ]
    agg = aggregate_layers(results, labels)
    assert agg["queries_scored"] == 0
    assert agg["queries_no_cold_relevant"] == 1
    assert agg["by_layer"]["B1_kb"]["cold_relevant_recall"] is None
