"""tests/test_kart_lane_guard.py"""
from core.kart_lane_guard import lane_mismatch_warning, suggest_lane
from core.kart_lanes import KART_LANE_BATCH, KART_LANE_FAST


def test_suggest_lane_batch_for_intake():
    assert suggest_lane("python3 scripts/promote_intake.py --days=7") == KART_LANE_BATCH


def test_suggest_lane_fast_for_git():
    assert suggest_lane("cd /repo && git status") == KART_LANE_FAST


def test_lane_mismatch_warning_on_heavy_fast():
    warn = lane_mismatch_warning("python3 auto_dream.py run\n# allow_localhost", "fast")
    assert warn is not None
    assert warn["suggested_lane"] == KART_LANE_BATCH
    assert warn["lane"] == KART_LANE_FAST


def test_lane_mismatch_warning_absent_on_batch():
    assert lane_mismatch_warning("python3 auto_dream.py run", "batch") is None
