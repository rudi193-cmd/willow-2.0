"""SCRATCH / DRAFT — TDD spec for the planned core/skill_mastery.py (Extension #1)
and the skill_mastery MCP tool (Extension #2). Written ahead of implementation.

Mirrors the structure of tests/test_s_tier_tools.py:
  - REPO_ROOT on sys.path
  - fixtures that set the one required env var (here WILLOW_STORE_ROOT) and import
    the module under test, the way `split_identifier` / `policy_check` do
  - test classes grouping behaviour
  - the async MCP tool's inner ranking tested as a plain mirror function
    (`_weakest`), exactly as test_s_tier_tools mirrors env_check._check()
    (`_compute_delta`) and diagnostic_summary._diag() (`_compute_new_diags`)

NOTE: lives in scratch/, NOT tests/ — pytest testpaths=["tests"], so CI does not
collect this. It targets core/skill_mastery.py, which does not exist yet. Run it
by hand once #1 lands:  python -m pytest scratch/test_skill_mastery.py
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = str(Path(__file__).parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def store_root(tmp_path, monkeypatch):
    """Isolate SOIL in a tmp store. Mirrors the env fixtures in
    test_s_tier_tools.py (monkeypatch a required env var per test).
    soil._root() reads WILLOW_STORE_ROOT at call time, so this isolates each test.
    """
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path / "store"))
    return tmp_path


@pytest.fixture
def sm(store_root):
    """Import the (planned) skill_mastery module after the store env is set."""
    import core.skill_mastery as _mod
    return _mod


# ── record(): online update + persistence (Extension #1) ─────────────────────

class TestRecord:
    def test_seeds_defaults_for_new_skill(self, sm):
        rec = sm.record("skill/a", correct=True)
        assert rec["skill_id"] == "skill/a"
        assert rec["opportunities"] == 1
        # the four BKT params are present and probabilistic
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
        for _ in range(50):
            rec = sm.record("skill/a", correct=True, history_cap=10)
        assert len(rec["history"]) <= 10

    def test_refit_updates_params(self, sm):
        # A skill answered correctly every time should, after a refit, learn a
        # higher prior/learn than the seeded defaults.
        seeded = sm.record("skill/a", correct=True, refit_every=5)["params"]
        last = seeded
        for _ in range(9):
            last = sm.record("skill/a", correct=True, refit_every=5)["params"]
        # params moved off the defaults once enough history accrued
        assert last != seeded


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
        # no explicit "success" key → fall back to result in outcomes._SUCCESS
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


# ── skill_mastery(weakest=N) inner ranking (Extension #2) ─────────────────────

class TestWeakestRanking:
    """Test the tool's ranking independently of the async tool + sap_gate,
    the way test_s_tier_tools mirrors env_check / diagnostic_summary inners."""

    def _weakest(self, records: list[dict], n: int) -> list[dict]:
        """Mirrors the inner ranking of skill_mastery(weakest=N)."""
        ranked = sorted(records, key=lambda r: r["p_known"])
        return [{"skill_id": r["skill_id"], "mastery": r["p_known"]}
                for r in ranked[:n]]

    def test_orders_ascending_by_mastery(self):
        records = [
            {"skill_id": "hi", "p_known": 0.92},
            {"skill_id": "lo", "p_known": 0.11},
            {"skill_id": "mid", "p_known": 0.50},
        ]
        out = self._weakest(records, 3)
        assert [r["skill_id"] for r in out] == ["lo", "mid", "hi"]

    def test_limit_respected(self):
        records = [{"skill_id": f"s{i}", "p_known": i / 10} for i in range(10)]
        out = self._weakest(records, 3)
        assert len(out) == 3
        assert out[0]["skill_id"] == "s0"

    def test_empty_returns_empty(self):
        assert self._weakest([], 5) == []
