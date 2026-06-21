"""Tests for core/jeles_verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.jeles_verify import _parse_claim_lines, verify_claims


def _stub(text):
    return lambda system, history, user: text


def test_parse_claim_lines_basic():
    raw = "CLAIM: The sky is blue || SOURCES: 1, 3\nCLAIM: Water is wet || SOURCES: NONE"
    assert _parse_claim_lines(raw) == [("The sky is blue", [1, 3]), ("Water is wet", [])]


def test_parse_tolerates_brackets_and_noise():
    raw = "preamble\nCLAIM: X happened || SOURCES: [2] and [2]\nnot a claim line"
    assert _parse_claim_lines(raw) == [("X happened", [2])]  # de-duped, bracket digits


def test_verdicts_cross_source():
    citations = [
        {"n": 1, "source": "NASA"},
        {"n": 2, "source": "arXiv"},
        {"n": 3, "source": "NASA"},
    ]
    llm = _stub(
        "CLAIM: corroborated claim || SOURCES: 1,2\n"   # NASA + arXiv -> 2 distinct
        "CLAIM: single claim || SOURCES: 1,3\n"         # NASA + NASA  -> 1 distinct
        "CLAIM: unsupported claim || SOURCES: NONE\n"
    )
    out = verify_claims("some answer", "sources block", citations, llm)
    verdicts = {c["claim"]: c["verdict"] for c in out["claims"]}
    assert verdicts["corroborated claim"] == "corroborated"
    assert verdicts["single claim"] == "single_source"
    assert verdicts["unsupported claim"] == "unsupported"
    assert out["summary"] == {
        "total": 3, "corroborated": 1, "single_source": 1, "unsupported": 1,
    }


def test_invalid_source_numbers_dropped():
    citations = [{"n": 1, "source": "NASA"}]
    out = verify_claims("a", "s", citations, _stub("CLAIM: bad ref || SOURCES: 1, 9"))
    claim = out["claims"][0]
    assert claim["sources"] == [1]            # 9 is not a real citation
    assert claim["verdict"] == "single_source"


def test_empty_inputs_short_circuit():
    assert verify_claims("", "", [], _stub(""))["summary"]["total"] == 0
    assert verify_claims("ans", "src", [], _stub("CLAIM: x || SOURCES: 1"))["summary"]["total"] == 0


def test_llm_failure_is_caught():
    def boom(system, history, user):
        raise RuntimeError("llm down")
    out = verify_claims("a", "s", [{"n": 1, "source": "NASA"}], boom)
    assert out["summary"]["total"] == 0
    assert "error" in out["summary"]
