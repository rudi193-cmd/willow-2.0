"""
tests/test_review/test_dispatcher.py — unit tests for willow/review/dispatcher.py
b17: REVW1  ΔΣ=42

Tests verify:
  - CONCERNS list is the canonical 5
  - _dedup_key is deterministic and tuple-typed
  - _validate_finding rejects findings with missing required fields
  - _dedup_findings: higher-confidence finding wins on collision
  - _dedup_findings: cross-agent collision resolved correctly
  - dispatch_review: unknown concern raises ValueError
  - dispatch_review: stub returns zero findings (no real agents wired)
  - dispatch_review: methodology envelope is populated
  - dedup_findings standalone utility works on flat list
  - cross-session dedup filters prior_findings correctly
"""
import unittest

from willow.review.dispatcher import (
    CONCERNS,
    _dedup_key,
    _validate_finding,
    _dedup_findings,
    dispatch_review,
    dedup_findings,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_finding(
    file="src/auth.py",
    line_start=10,
    line_end=15,
    concern="security",
    title="SQL injection",
    description="User input passed directly to query.",
    severity="high",
    confidence=80,
    agent="review-security",
    **extra,
) -> dict:
    f = {
        "file": file,
        "line_start": line_start,
        "line_end": line_end,
        "concern": concern,
        "title": title,
        "description": description,
        "severity": severity,
        "confidence": confidence,
        "agent": agent,
    }
    f.update(extra)
    return f


# ---------------------------------------------------------------------------
# CONCERNS list
# ---------------------------------------------------------------------------

class TestConcernsList(unittest.TestCase):
    def test_has_5_concerns(self):
        self.assertEqual(len(CONCERNS), 5)

    def test_required_concerns_present(self):
        for c in ("security", "correctness", "impact", "test_coverage", "style"):
            self.assertIn(c, CONCERNS)


# ---------------------------------------------------------------------------
# _dedup_key
# ---------------------------------------------------------------------------

class TestDedupKey(unittest.TestCase):
    def test_returns_tuple(self):
        f = _make_finding()
        key = _dedup_key(f)
        self.assertIsInstance(key, tuple)

    def test_same_finding_same_key(self):
        f1 = _make_finding()
        f2 = _make_finding()
        self.assertEqual(_dedup_key(f1), _dedup_key(f2))

    def test_different_file_different_key(self):
        f1 = _make_finding(file="src/auth.py")
        f2 = _make_finding(file="src/db.py")
        self.assertNotEqual(_dedup_key(f1), _dedup_key(f2))

    def test_different_line_different_key(self):
        f1 = _make_finding(line_start=10)
        f2 = _make_finding(line_start=20)
        self.assertNotEqual(_dedup_key(f1), _dedup_key(f2))

    def test_different_concern_different_key(self):
        f1 = _make_finding(concern="security")
        f2 = _make_finding(concern="correctness")
        self.assertNotEqual(_dedup_key(f1), _dedup_key(f2))

    def test_key_is_4_tuple(self):
        f = _make_finding()
        key = _dedup_key(f)
        self.assertEqual(len(key), 4)  # (file, line_start, line_end, concern)

    def test_missing_fields_dont_crash(self):
        # Findings with missing fields should not raise — return default values
        key = _dedup_key({})
        self.assertIsInstance(key, tuple)


# ---------------------------------------------------------------------------
# _validate_finding
# ---------------------------------------------------------------------------

class TestValidateFinding(unittest.TestCase):
    def test_valid_finding_passes(self):
        f = _make_finding()
        ok, warns = _validate_finding(f, "review-security")
        self.assertTrue(ok)
        self.assertEqual(warns, [])

    def test_missing_file_rejected(self):
        f = _make_finding()
        del f["file"]
        ok, warns = _validate_finding(f, "review-security")
        self.assertFalse(ok)
        self.assertTrue(any("file" in w for w in warns))

    def test_missing_title_rejected(self):
        f = _make_finding()
        del f["title"]
        ok, warns = _validate_finding(f, "review-security")
        self.assertFalse(ok)

    def test_empty_description_rejected(self):
        f = _make_finding(description="")
        ok, warns = _validate_finding(f, "review-security")
        self.assertFalse(ok)

    def test_invalid_severity_warns_but_keeps(self):
        f = _make_finding(severity="extreme")
        ok, warns = _validate_finding(f, "review-security")
        self.assertTrue(ok)  # kept with warning
        self.assertTrue(any("severity" in w for w in warns))

    def test_confidence_out_of_range_rejected(self):
        f = _make_finding(confidence=150)
        ok, warns = _validate_finding(f, "review-security")
        self.assertFalse(ok)

    def test_confidence_zero_is_valid(self):
        f = _make_finding(confidence=0)
        ok, warns = _validate_finding(f, "review-security")
        self.assertTrue(ok)

    def test_confidence_100_is_valid(self):
        f = _make_finding(confidence=100)
        ok, warns = _validate_finding(f, "review-security")
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# _dedup_findings
# ---------------------------------------------------------------------------

class TestDedupFindings(unittest.TestCase):
    def test_no_collision_preserves_all(self):
        f1 = _make_finding(file="src/auth.py", concern="security")
        f2 = _make_finding(file="src/db.py", concern="correctness")
        merged, dupes = _dedup_findings({"a": [f1], "b": [f2]})
        self.assertEqual(len(merged), 2)
        self.assertEqual(dupes, 0)

    def test_collision_high_confidence_wins(self):
        f_high = _make_finding(confidence=90, agent="a")
        f_low = _make_finding(confidence=50, agent="b")
        merged, dupes = _dedup_findings({"a": [f_high], "b": [f_low]})
        self.assertEqual(len(merged), 1)
        self.assertEqual(dupes, 1)
        self.assertEqual(merged[0]["confidence"], 90)
        self.assertEqual(merged[0]["agent"], "a")

    def test_collision_low_confidence_loses(self):
        f_low = _make_finding(confidence=30, agent="loser")
        f_high = _make_finding(confidence=85, agent="winner")
        merged, dupes = _dedup_findings({"loser": [f_low], "winner": [f_high]})
        self.assertEqual(merged[0]["agent"], "winner")

    def test_collision_severity_tiebreak(self):
        # Same confidence — higher severity wins
        f_high = _make_finding(confidence=70, severity="critical", agent="a")
        f_low = _make_finding(confidence=70, severity="low", agent="b")
        merged, dupes = _dedup_findings({"a": [f_high], "b": [f_low]})
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["severity"], "critical")

    def test_three_agents_same_finding(self):
        f1 = _make_finding(confidence=60, agent="a")
        f2 = _make_finding(confidence=75, agent="b")
        f3 = _make_finding(confidence=50, agent="c")
        merged, dupes = _dedup_findings({"a": [f1], "b": [f2], "c": [f3]})
        self.assertEqual(len(merged), 1)
        self.assertEqual(dupes, 2)
        self.assertEqual(merged[0]["agent"], "b")

    def test_agent_field_injected(self):
        f = _make_finding()
        del f["agent"]
        merged, _ = _dedup_findings({"review-security": [f]})
        self.assertEqual(merged[0]["agent"], "review-security")

    def test_empty_input(self):
        merged, dupes = _dedup_findings({})
        self.assertEqual(merged, [])
        self.assertEqual(dupes, 0)


# ---------------------------------------------------------------------------
# dispatch_review
# ---------------------------------------------------------------------------

class TestDispatchReview(unittest.TestCase):
    DUMMY_DIFF = "--- a/auth.py\n+++ b/auth.py\n@@ -10,3 +10,4 @@\n+    return user_input\n"

    def test_unknown_concern_raises(self):
        with self.assertRaises(ValueError):
            dispatch_review(self.DUMMY_DIFF, concerns=["nonexistent"])

    def test_returns_dict_with_findings(self):
        result = dispatch_review(self.DUMMY_DIFF)
        self.assertIn("findings", result)
        self.assertIn("methodology", result)

    def test_methodology_has_concerns_dispatched(self):
        result = dispatch_review(self.DUMMY_DIFF, concerns=["security", "correctness"])
        self.assertIn("concerns_dispatched", result["methodology"])
        self.assertEqual(result["methodology"]["concerns_dispatched"], ["security", "correctness"])

    def test_stub_returns_zero_findings(self):
        # The stub _invoke_concern_agent returns []
        result = dispatch_review(self.DUMMY_DIFF)
        self.assertEqual(result["findings"], [])

    def test_session_sha_auto_generated(self):
        # Should not raise when session_sha is omitted
        result = dispatch_review(self.DUMMY_DIFF)
        self.assertIn("findings", result)

    def test_custom_session_sha(self):
        result = dispatch_review(self.DUMMY_DIFF, session_sha="abc1234")
        self.assertIn("findings", result)

    def test_methodology_duplicates_resolved(self):
        result = dispatch_review(self.DUMMY_DIFF)
        self.assertIn("duplicates_resolved", result["methodology"])
        self.assertIsInstance(result["methodology"]["duplicates_resolved"], int)

    def test_cross_session_dedup_with_prior_findings(self):
        # Prior finding matches the stub's (empty) output — nothing filtered
        prior = [_make_finding(concern="security")]
        result = dispatch_review(self.DUMMY_DIFF, prior_findings=prior)
        # Stub returns nothing, so cross_session_deduped should be 0
        self.assertEqual(result["methodology"]["cross_session_deduped"], 0)

    def test_all_concerns_dispatched_by_default(self):
        result = dispatch_review(self.DUMMY_DIFF)
        self.assertEqual(
            set(result["methodology"]["concerns_dispatched"]),
            set(CONCERNS)
        )

    def test_subset_concerns(self):
        result = dispatch_review(self.DUMMY_DIFF, concerns=["security"])
        self.assertEqual(result["methodology"]["concerns_dispatched"], ["security"])


# ---------------------------------------------------------------------------
# dedup_findings standalone utility
# ---------------------------------------------------------------------------

class TestDedupFindingsUtility(unittest.TestCase):
    def test_flat_list_deduped(self):
        f1 = _make_finding(confidence=80, agent="a")
        f2 = _make_finding(confidence=60, agent="b")  # same key
        f3 = _make_finding(file="other.py", concern="correctness", agent="c")
        deduplicated, count = dedup_findings([f1, f2, f3])
        self.assertEqual(len(deduplicated), 2)
        self.assertEqual(count, 1)

    def test_empty_list(self):
        deduped, count = dedup_findings([])
        self.assertEqual(deduped, [])
        self.assertEqual(count, 0)

    def test_no_duplicates_unchanged(self):
        f1 = _make_finding(file="a.py", concern="security")
        f2 = _make_finding(file="b.py", concern="correctness")
        deduped, count = dedup_findings([f1, f2])
        self.assertEqual(len(deduped), 2)
        self.assertEqual(count, 0)

    def test_single_finding_unchanged(self):
        f = _make_finding()
        deduped, count = dedup_findings([f])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
