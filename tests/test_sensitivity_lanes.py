"""Sensitivity veto axis — lane defaults, fail-closed resolution, taint rule.

ADR-20260702-router-sensitivity-veto step 1. Pure-function coverage plus
migration-list presence checks; DB round-trips ride the existing pg suites.
"""
import pytest

from core.canonical_lanes import (
    CANONICAL_LANES,
    SENSITIVE_LANES,
    SENSITIVITY_OPEN,
    SENSITIVITY_SENSITIVE,
    atoms_taint,
    effective_sensitivity,
    lane_default_sensitivity,
    max_sensitivity,
    normalize_sensitivity,
)


class TestNormalizeSensitivity:
    def test_empty_and_none_mean_no_override(self):
        assert normalize_sensitivity(None) is None
        assert normalize_sensitivity("") is None
        assert normalize_sensitivity("   ") is None

    def test_canonical_values_pass(self):
        assert normalize_sensitivity("open") == SENSITIVITY_OPEN
        assert normalize_sensitivity("sensitive") == SENSITIVITY_SENSITIVE

    def test_case_and_whitespace_normalized(self):
        assert normalize_sensitivity(" Sensitive ") == SENSITIVITY_SENSITIVE
        assert normalize_sensitivity("OPEN") == SENSITIVITY_OPEN

    def test_invalid_value_raises_not_defaults(self):
        with pytest.raises(ValueError):
            normalize_sensitivity("secret")
        with pytest.raises(ValueError):
            normalize_sensitivity("public")


class TestLaneDefaults:
    def test_ratified_sensitive_lanes(self):
        assert SENSITIVE_LANES == {"personal", "epstein_network", "rh-dirty"}
        for lane in SENSITIVE_LANES:
            assert lane in CANONICAL_LANES
            assert lane_default_sensitivity(lane) == SENSITIVITY_SENSITIVE

    def test_open_lanes(self):
        for lane in CANONICAL_LANES - SENSITIVE_LANES:
            assert lane_default_sensitivity(lane) == SENSITIVITY_OPEN

    def test_unknown_lane_fails_closed(self):
        assert lane_default_sensitivity("not-a-lane") == SENSITIVITY_SENSITIVE
        assert lane_default_sensitivity("") == SENSITIVITY_SENSITIVE
        assert lane_default_sensitivity(None) == SENSITIVITY_SENSITIVE


class TestEffectiveSensitivity:
    def test_explicit_wins_both_directions(self):
        assert effective_sensitivity("personal", "open") == SENSITIVITY_OPEN
        assert effective_sensitivity("willow", "sensitive") == SENSITIVITY_SENSITIVE

    def test_null_falls_to_lane_default(self):
        assert effective_sensitivity("personal", None) == SENSITIVITY_SENSITIVE
        assert effective_sensitivity("willow", None) == SENSITIVITY_OPEN

    def test_garbage_stored_value_fails_closed_to_lane_default(self):
        assert effective_sensitivity("willow", "banana") == SENSITIVITY_OPEN
        assert effective_sensitivity("personal", "banana") == SENSITIVITY_SENSITIVE

    def test_unknown_lane_and_null_is_sensitive(self):
        assert effective_sensitivity(None, None) == SENSITIVITY_SENSITIVE


class TestTaint:
    def test_max_sensitivity(self):
        assert max_sensitivity([]) == SENSITIVITY_OPEN
        assert max_sensitivity(["open", "open"]) == SENSITIVITY_OPEN
        assert max_sensitivity(["open", "sensitive"]) == SENSITIVITY_SENSITIVE
        assert max_sensitivity([None, "open"]) == SENSITIVITY_OPEN

    def test_atoms_taint_uses_effective_resolution(self):
        open_atom = {"project": "willow", "sensitivity": None}
        tainted = {"project": "personal", "sensitivity": None}
        assert atoms_taint([open_atom]) == SENSITIVITY_OPEN
        assert atoms_taint([open_atom, tainted]) == SENSITIVITY_SENSITIVE

    def test_atoms_taint_explicit_override_respected(self):
        cleared = {"project": "personal", "sensitivity": "open"}
        assert atoms_taint([cleared]) == SENSITIVITY_OPEN

    def test_atoms_taint_unknown_lane_fails_closed(self):
        assert atoms_taint([{"project": "mystery"}]) == SENSITIVITY_SENSITIVE


class TestMigrationsWired:
    def test_migrations_contain_sensitivity_ddl(self):
        from core.pg_bridge import _MIGRATIONS
        joined = "\n".join(_MIGRATIONS)
        assert "ADD COLUMN IF NOT EXISTS sensitivity TEXT" in joined
        assert "knowledge_sensitivity_check" in joined
        assert "idx_knowledge_sensitivity" in joined

    def test_backfill_matches_ratified_lane_defaults(self):
        from core.pg_bridge import _MIGRATIONS
        backfill = [m for m in _MIGRATIONS if "UPDATE knowledge SET sensitivity = CASE" in m]
        assert len(backfill) == 1
        stmt = backfill[0]
        for lane in SENSITIVE_LANES:
            assert f"'{lane}'" in stmt
        for lane in CANONICAL_LANES - SENSITIVE_LANES:
            assert f"'{lane}'" in stmt
        assert "ELSE 'sensitive'" in stmt          # fail-closed for off-lane rows
        assert "WHERE sensitivity IS NULL" in stmt  # never clobbers overrides

    def test_select_cols_include_sensitivity(self):
        import inspect
        from core.pg_bridge import PgBridge
        src = inspect.getsource(PgBridge._knowledge_select_cols)
        assert '"sensitivity"' in src


class TestSidecarSensitivity:
    """ADR-20260702 step 2 — jeles/opus columns, veto filters, real taint."""

    def test_sidecar_migrations_present(self):
        from core.pg_bridge import _MIGRATIONS
        joined = "\n".join(_MIGRATIONS)
        assert "ALTER TABLE jeles_atoms ADD COLUMN IF NOT EXISTS sensitivity TEXT" in joined
        assert "ALTER TABLE opus_atoms ADD COLUMN IF NOT EXISTS sensitivity TEXT" in joined
        assert "jeles_sensitivity_check" in joined
        assert "opus_sensitivity_check" in joined
        assert "idx_jeles_atoms_sensitivity" in joined
        assert "idx_opus_atoms_sensitivity" in joined

    def test_jeles_backfill_all_open_ratified(self):
        from core.pg_bridge import _MIGRATIONS
        stmts = [m for m in _MIGRATIONS
                 if "UPDATE jeles_atoms SET sensitivity" in m]
        assert len(stmts) == 1
        assert "'open'" in stmts[0]
        assert "WHERE sensitivity IS NULL" in stmts[0]

    def test_opus_backfill_file_index_open_else_sensitive(self):
        from core.pg_bridge import _MIGRATIONS
        stmts = [m for m in _MIGRATIONS
                 if "UPDATE opus_atoms SET sensitivity" in m]
        assert len(stmts) == 1
        assert "WHEN domain = 'file_index' THEN 'open'" in stmts[0]
        assert "ELSE 'sensitive'" in stmts[0]
        assert "WHERE sensitivity IS NULL" in stmts[0]

    def test_sidecar_search_filters_fail_closed(self):
        import inspect
        from core.pg_bridge import PgBridge
        for fn in (PgBridge.search_jeles_semantic, PgBridge.jeles_keyword_search,
                   PgBridge.search_opus_semantic, PgBridge.search_opus):
            src = inspect.getsource(fn)
            assert "include_sensitive" in src, fn.__name__
            assert "COALESCE(sensitivity, 'sensitive')" in src, fn.__name__

    def test_shape_rows_pass_sensitivity_through(self):
        import inspect
        from core.pg_bridge import PgBridge
        assert '"sensitivity"' in inspect.getsource(PgBridge._knowledge_shape_rows)

    def test_atoms_taint_on_sidecar_rows(self):
        tagged_open = {"sensitivity": "open"}          # no project — value wins
        untagged = {}                                   # no project, no value → closed
        assert atoms_taint([tagged_open]) == SENSITIVITY_OPEN
        assert atoms_taint([tagged_open, untagged]) == SENSITIVITY_SENSITIVE
