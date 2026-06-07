# b17: SKMS1  ΔΣ=42
"""Tests for core/skill_mastery.py — live BKT mastery tracking per skill.

SOIL is isolated per test via WILLOW_STORE_ROOT (soil._root() reads it at call
time), the same monkeypatch-an-env idiom used in tests/test_s_tier_tools.py.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = str(Path(__file__).parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.fixture
def store_root(tmp_path, monkeypatch):
    """Isolate SOIL in a tmp store for the duration of one test."""
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path / "store"))
    return tmp_path


@pytest.fixture
def sm(store_root):
    """Import the skill_mastery module after the store env is set."""
    import core.skill_mastery as _mod
    return _mod


# ── record(): online update + persistence ────────────────────────────────────

class TestRecord:
    def test_seeds_defaults_for_new_skill(self, sm):
        rec = sm.record("skill/a", correct=True)
        assert rec["skill_id"] == "skill/a"
        assert rec["opportunities"] == 1
        for k in ("prior", "learn", "guess", "slip"):
            assert 0.0 <= rec["params"][k] <= 1.0
        assert 0.0 <= rec["p_known"] <= 1.0

    def test_correct_observations_raise_mastery_monotonically(self, sm):
        seen = [sm.record("skill/a", correct=True)["p_known"] for _ in range(5)]
        assert all(seen[i] <= seen[i + 1] + 1e-12 for i in range(len(seen) - 1))
        assert seen[-1] > seen[0]

    def test_incorrect_is_lower_than_correct(self, sm):
        up = sm.record("skill/up", correct=True)["p_known"]
        down = sm.record("skill/down", correct=False)["p_known"]
        assert down < up

    def test_persists_across_calls(self, sm):
        sm.record("skill/a", correct=True)
        sm.record("skill/a", correct=False)
        snap = sm.mastery("skill/a")
        assert snap is not None
        assert snap["opportunities"] == 2

    def test_history_is_capped(self, sm):
        rec = None
        for _ in range(50):
            rec = sm.record("skill/a", correct=True, history_cap=10)
        assert len(rec["history"]) <= 10

    def test_refit_updates_params(self, sm):
        seeded = sm.record("skill/a", correct=True, refit_every=5)["params"]
        last = seeded
        for _ in range(9):
            last = sm.record("skill/a", correct=True, refit_every=5)["params"]
        # params moved off the seeded defaults once a refit fired
        assert last != seeded
        assert "refit_at" in sm.mastery("skill/a")


# ── record_outcome(): adapter over core/outcomes.py results ───────────────────

class TestRecordOutcome:
    def test_success_true_maps_to_correct(self, sm):
        via_outcome = sm.record_outcome("skill/x", {"success": True})["p_known"]
        via_bool = sm.record("skill/y", correct=True)["p_known"]
        assert via_outcome == pytest.approx(via_bool)

    def test_result_failed_maps_to_incorrect(self, sm):
        via_outcome = sm.record_outcome("skill/x", {"result": "failed"})["p_known"]
        via_bool = sm.record("skill/y", correct=False)["p_known"]
        assert via_outcome == pytest.approx(via_bool)

    def test_result_satisfied_maps_to_correct(self, sm):
        # no "success" key → fall back to result in outcomes._SUCCESS
        via_outcome = sm.record_outcome("skill/x", {"result": "satisfied"})["p_known"]
        via_bool = sm.record("skill/y", correct=True)["p_known"]
        assert via_outcome == pytest.approx(via_bool)


# ── mastery() / all_mastery(): read-only snapshots ───────────────────────────

class TestSnapshot:
    def test_unknown_skill_returns_none(self, sm):
        assert sm.mastery("never/seen") is None

    def test_snapshot_matches_last_record(self, sm):
        rec = sm.record("skill/a", correct=True)
        snap = sm.mastery("skill/a")
        assert snap["p_known"] == pytest.approx(rec["p_known"])

    def test_all_mastery_lists_every_skill(self, sm):
        sm.record("skill/a", correct=True)
        sm.record("skill/b", correct=False)
        ids = {r["skill_id"] for r in sm.all_mastery()}
        assert ids == {"skill/a", "skill/b"}


# ── weakest(): drill ranking for #3 ──────────────────────────────────────────

class TestWeakest:
    def _seed(self, sm):
        sm.record("skill/lo", correct=False)             # lowest mastery
        sm.record("skill/mid", correct=True)             # middle
        for _ in range(5):
            sm.record("skill/hi", correct=True)          # highest

    def test_orders_ascending_by_mastery(self, sm):
        self._seed(sm)
        out = sm.weakest(3)
        assert [r["skill_id"] for r in out] == ["skill/lo", "skill/mid", "skill/hi"]

    def test_limit_respected(self, sm):
        self._seed(sm)
        out = sm.weakest(2)
        assert len(out) == 2
        assert out[0]["skill_id"] == "skill/lo"

    def test_threshold_filters_mastered(self, sm):
        self._seed(sm)
        out = sm.weakest(5, threshold=0.5)
        ids = [r["skill_id"] for r in out]
        assert "skill/lo" in ids
        assert "skill/hi" not in ids  # well above threshold

    def test_empty_store_returns_empty(self, sm):
        assert sm.weakest(5) == []
