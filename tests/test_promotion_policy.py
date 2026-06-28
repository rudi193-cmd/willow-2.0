"""Unit tests for core.promotion_policy.select_promotion_ids (no DB)."""
import pytest

from core.promotion_policy import select_promotion_ids


def _rows(*specs):
    """specs: (id, cosine) tuples; cosine None -> field absent."""
    out = []
    for rid, cos in specs:
        row = {"id": rid}
        if cos is not None:
            row["_cosine_sim"] = cos
        out.append(row)
    return out


def test_relgate_keeps_only_hits_above_floor():
    rows = _rows(("a", 0.80), ("b", 0.55), ("c", 0.40), ("d", 0.50))
    # default floor 0.5 -> a, b, d (>= 0.5), not c
    assert select_promotion_ids(rows, mode="relgate", floor=0.5) == ["a", "b", "d"]


def test_relgate_is_rank_independent():
    # a low-rank but on-topic atom is promoted; a high-rank off-topic one is not
    rows = _rows(("top", 0.30), ("mid", 0.30), ("deep", 0.90))
    assert select_promotion_ids(rows, mode="relgate", floor=0.5) == ["deep"]


def test_relgate_empty_when_cosine_present_but_none_clear_floor():
    rows = _rows(("a", 0.30), ("b", 0.10))
    assert select_promotion_ids(rows, mode="relgate", floor=0.5) == []


def test_relgate_falls_back_to_top_n_without_cosine():
    # keyword/degraded path: no row carries _cosine_sim -> top_n
    rows = _rows(("a", None), ("b", None), ("c", None), ("d", None))
    assert select_promotion_ids(rows, mode="relgate", top_n=3) == ["a", "b", "c"]


def test_topn_mode():
    rows = _rows(("a", 0.9), ("b", 0.9), ("c", 0.9), ("d", 0.9))
    assert select_promotion_ids(rows, mode="topn", top_n=2) == ["a", "b"]


def test_rows_without_id_skipped():
    rows = [{"_cosine_sim": 0.9}, {"id": "b", "_cosine_sim": 0.9}]
    assert select_promotion_ids(rows, mode="relgate", floor=0.5) == ["b"]


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("WILLOW_PROMOTE_MODE", "topn")
    monkeypatch.setenv("WILLOW_PROMOTE_TOP_N", "1")
    rows = _rows(("a", 0.9), ("b", 0.9))
    assert select_promotion_ids(rows) == ["a"]


def test_env_floor_override(monkeypatch):
    monkeypatch.setenv("WILLOW_PROMOTE_MODE", "relgate")
    monkeypatch.setenv("WILLOW_PROMOTE_RELGATE_FLOOR", "0.7")
    rows = _rows(("a", 0.8), ("b", 0.6))
    assert select_promotion_ids(rows) == ["a"]


def test_default_mode_is_relgate(monkeypatch):
    monkeypatch.delenv("WILLOW_PROMOTE_MODE", raising=False)
    rows = _rows(("a", 0.9), ("b", 0.2))
    assert select_promotion_ids(rows) == ["a"]


@pytest.mark.parametrize("bad", [None, "nan-ish", object()])
def test_bad_cosine_values_excluded(bad):
    rows = [{"id": "a", "_cosine_sim": bad}, {"id": "b", "_cosine_sim": 0.9}]
    # 'a' has a cosine key (so has_cosine=True) but unparseable/None -> excluded
    assert select_promotion_ids(rows, mode="relgate", floor=0.5) == ["b"]
