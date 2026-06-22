"""Regression tests for nest_seed.classify date/receipt heuristics.

Guards the two false-positive classes found on the real ~/Desktop/Nest dump:
  - version strings ("2.1.170") tagged as dates
  - JSON/config blobs tagged as receipts off a single weak keyword
"""
from sandbox.nest_seed.classify import _plausible_date, _is_receipt, classify


def test_plausible_date_rejects_semver():
    for v in ("2.1.170", "2.1.172", "2.1.17", "1.2.3", "0.0.1"):
        assert _plausible_date(v) is False, v


def test_plausible_date_accepts_real_dates():
    for d in ("2026-05-31", "2024-06-21", "12/31/2024", "6-21-2024",
              "21/6/24", "31.12.2024", "2019.10.15", "June 21, 2024"):
        assert _plausible_date(d) is True, d


def test_plausible_date_rejects_out_of_range_and_nondates():
    for s in ("13/45/99", "version 1, 2024", "99.99.99"):
        assert _plausible_date(s) is False, s


def test_receipt_strong_keyword_alone():
    assert _is_receipt("INVOICE #4471")
    assert _is_receipt("Subtotal: 12.00")


def test_receipt_weak_keyword_needs_currency():
    assert _is_receipt("Total: $13.00  Tax: $1.00")
    assert not _is_receipt('{"total_tokens": 512, "changes": 3, "tax": null}')
    assert not _is_receipt("cash and change in the river")


def test_classify_does_not_emit_version_dates():
    text = '{"version": "2.1.170", "build": "2.1.172"}'
    dates = [f.content for f in classify(text) if f.fragment_type == "date"]
    assert dates == [], dates


def test_classify_json_blob_is_not_receipt():
    text = '{"total": 5, "tax": 0, "change": "none"}'
    assert not any(f.fragment_type == "receipt" for f in classify(text))
