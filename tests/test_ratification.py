"""Unit tests for core.ratification.classify_ratification_class()."""
import pytest

from core.ratification import classify_ratification_class


# ── Evidence-based cases ──────────────────────────────────────────────────────

def test_code_source_is_evidence():
    rec = {"source": "code_graph_scan", "tier": "observed", "confidence": 0.7}
    assert classify_ratification_class(rec) == "evidence_based"


def test_drift_source_is_evidence():
    rec = {"source": "kb_truth_drift", "tier": "frontier", "confidence": 0.8}
    assert classify_ratification_class(rec) == "evidence_based"


def test_test_source_is_evidence():
    rec = {"source": "ci_test_run", "tier": "observed", "confidence": 0.6}
    assert classify_ratification_class(rec) == "evidence_based"


def test_fetched_high_confidence_is_evidence():
    rec = {"source": "web_search", "tier": "fetched", "confidence": 0.92}
    assert classify_ratification_class(rec) == "evidence_based"


def test_verified_high_confidence_is_evidence():
    rec = {"source": "", "tier": "verified", "confidence": 0.95}
    assert classify_ratification_class(rec) == "evidence_based"


def test_pattern_category_is_evidence():
    rec = {"category": "pattern", "tier": "observed", "confidence": 0.75, "source": ""}
    assert classify_ratification_class(rec) == "evidence_based"


def test_reference_category_is_evidence():
    rec = {"category": "reference", "tier": "frontier", "confidence": 0.80, "source": ""}
    assert classify_ratification_class(rec) == "evidence_based"


# ── Judgment-based cases ──────────────────────────────────────────────────────

def test_canonical_tier_is_judgment():
    rec = {"tier": "canonical", "confidence": 0.99, "source": "code", "category": "pattern"}
    assert classify_ratification_class(rec) == "judgment_based"


def test_correction_category_is_judgment():
    rec = {"category": "correction", "tier": "verified", "confidence": 0.95, "source": "ci"}
    assert classify_ratification_class(rec) == "judgment_based"


def test_architecture_category_is_judgment():
    rec = {"category": "architecture", "source": "code", "confidence": 0.91}
    assert classify_ratification_class(rec) == "judgment_based"


def test_feedback_source_is_judgment():
    rec = {"source": "user_feedback", "tier": "verified", "confidence": 0.95}
    assert classify_ratification_class(rec) == "judgment_based"


def test_sean_source_is_judgment():
    rec = {"source": "sean_voice", "tier": "fetched", "confidence": 0.92}
    assert classify_ratification_class(rec) == "judgment_based"


def test_preference_source_is_judgment():
    rec = {"source": "preference_capture", "tier": "observed", "confidence": 0.88}
    assert classify_ratification_class(rec) == "judgment_based"


def test_fetched_below_threshold_is_judgment():
    rec = {"source": "", "tier": "fetched", "confidence": 0.80}
    assert classify_ratification_class(rec) == "judgment_based"


def test_empty_record_defaults_judgment():
    assert classify_ratification_class({}) == "judgment_based"


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_judgment_beats_evidence_source():
    """correction category wins even if source contains 'code'."""
    rec = {"category": "correction", "source": "code_review", "tier": "verified", "confidence": 0.95}
    assert classify_ratification_class(rec) == "judgment_based"


def test_canonical_tier_beats_evidence_source():
    rec = {"tier": "canonical", "source": "ci_pipeline", "confidence": 0.99}
    assert classify_ratification_class(rec) == "judgment_based"
