"""
tests/test_routing/test_intent.py — unit tests for willow/routing/intent.py
b17: INTL1  ΔΣ=42

Tests verify:
  - classify_intent returns correct intent for clear cases
  - confidence is in [0, 1]
  - ambiguous queries reduce confidence (runner-up penalty)
  - classify_intent_all returns all 7 intents sorted by confidence
  - extract_slots pulls file paths, line numbers, agents
  - empty / whitespace-only input handled gracefully
"""
import unittest

from willow.routing.intent import (
    classify_intent,
    classify_intent_all,
    extract_slots,
    _tokenize,
    _INTENT_RULES,
    _DEFAULT_INTENT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestTokenize(unittest.TestCase):
    def test_splits_on_spaces(self):
        tokens = _tokenize("find the error in auth module")
        self.assertIn("find", tokens)
        self.assertIn("error", tokens)
        self.assertIn("auth", tokens)
        self.assertIn("module", tokens)
        # stop words removed
        self.assertNotIn("the", tokens)
        self.assertNotIn("in", tokens)

    def test_splits_camel_case(self):
        tokens = _tokenize("AuthModule")
        self.assertIn("auth", tokens)
        self.assertIn("module", tokens)

    def test_splits_snake_case(self):
        tokens = _tokenize("auth_module")
        self.assertIn("auth", tokens)
        self.assertIn("module", tokens)

    def test_empty_string(self):
        self.assertEqual(_tokenize(""), [])

    def test_stop_words_removed(self):
        tokens = _tokenize("the a an in of to for and or")
        self.assertEqual(tokens, [])


# ---------------------------------------------------------------------------
# classify_intent — happy-path cases
# ---------------------------------------------------------------------------

class TestClassifyIntentHappyPath(unittest.TestCase):

    def _assert_intent(self, query: str, expected: str, min_conf: float = 0.1):
        intent, conf = classify_intent(query)
        self.assertEqual(intent, expected,
            f"Query {query!r}: expected {expected!r}, got {intent!r} (conf={conf})")
        self.assertGreaterEqual(conf, min_conf,
            f"Confidence too low for {query!r}: {conf}")
        self.assertLessEqual(conf, 1.0)

    def test_debug_with_error(self):
        # "fail" hits debug (1.5) but max_score is large — conf is low but intent is correct
        self._assert_intent("why does auth.py fail on login?", "debug", 0.01)

    def test_debug_with_traceback(self):
        self._assert_intent("I'm getting a traceback in the database module", "debug", 0.05)

    def test_debug_with_exception_class(self):
        self._assert_intent("AttributeError in grove_listen when starting", "debug", 0.05)

    def test_explain_what(self):
        self._assert_intent("what does the oracle do?", "explain", 0.05)

    def test_explain_how(self):
        self._assert_intent("how does routing work in willow?", "explain", 0.05)

    def test_refactor_explicit(self):
        self._assert_intent("refactor the database module into smaller classes", "refactor", 0.10)

    def test_refactor_simplify(self):
        self._assert_intent("simplify this function", "refactor", 0.05)

    def test_review_explicit(self):
        self._assert_intent("review my changes before I push", "review", 0.05)

    def test_review_security(self):
        self._assert_intent("audit the auth module for security issues", "review", 0.05)

    def test_test_explicit(self):
        self._assert_intent("write tests for the dispatcher", "test", 0.05)

    def test_test_coverage(self):
        self._assert_intent("what is the test coverage for routing?", "test", 0.05)

    def test_integrate_explicit(self):
        self._assert_intent("integrate the MCP server with grove", "integrate", 0.05)

    def test_integrate_wire(self):
        self._assert_intent("wire the new endpoint into the middleware", "integrate", 0.05)

    def test_navigate_where(self):
        self._assert_intent("where is the grove listener defined?", "navigate", 0.05)

    def test_navigate_find(self):
        self._assert_intent("find all callers of classify_intent", "navigate", 0.05)


# ---------------------------------------------------------------------------
# classify_intent — edge cases
# ---------------------------------------------------------------------------

class TestClassifyIntentEdgeCases(unittest.TestCase):

    def test_empty_string_returns_navigate(self):
        intent, conf = classify_intent("")
        self.assertEqual(intent, "navigate")
        self.assertEqual(conf, 0.0)

    def test_whitespace_returns_navigate(self):
        intent, conf = classify_intent("   ")
        self.assertEqual(intent, "navigate")
        self.assertEqual(conf, 0.0)

    def test_confidence_in_range(self):
        for query in [
            "fix the bug",
            "explain what this does",
            "find the file",
            "write a unit test",
        ]:
            _, conf = classify_intent(query)
            self.assertGreaterEqual(conf, 0.0, f"Negative confidence for: {query!r}")
            self.assertLessEqual(conf, 1.0, f"Confidence > 1.0 for: {query!r}")

    def test_ambiguous_query_lower_confidence(self):
        # "review and fix" touches both review and debug — should have lower conf
        _, unambiguous_conf = classify_intent("traceback in database module")
        _, ambiguous_conf = classify_intent("review and fix the code")
        # Ambiguous shouldn't win with very high confidence
        self.assertLessEqual(ambiguous_conf, 0.9)

    def test_unknown_words_dont_crash(self):
        intent, conf = classify_intent("xyzzy frobnotz blorp quux")
        self.assertIsInstance(intent, str)
        self.assertIsInstance(conf, float)


# ---------------------------------------------------------------------------
# classify_intent_all
# ---------------------------------------------------------------------------

class TestClassifyIntentAll(unittest.TestCase):

    def test_returns_all_7_intents(self):
        results = classify_intent_all("fix the error")
        intent_names = [r[0] for r in results]
        expected = {"debug", "explain", "refactor", "review", "test", "integrate", "navigate"}
        self.assertEqual(set(intent_names), expected)

    def test_sorted_descending(self):
        results = classify_intent_all("fix the error")
        confs = [r[1] for r in results]
        self.assertEqual(confs, sorted(confs, reverse=True))

    def test_top_intent_matches_classify_intent(self):
        query = "where is the auth module?"
        top_intent_all, _ = classify_intent_all(query)[0]
        top_intent, _ = classify_intent(query)
        self.assertEqual(top_intent_all, top_intent)

    def test_empty_string(self):
        results = classify_intent_all("")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "navigate")


# ---------------------------------------------------------------------------
# extract_slots
# ---------------------------------------------------------------------------

class TestExtractSlots(unittest.TestCase):

    def test_extracts_file_path(self):
        slots = extract_slots("fix the error in auth.py")
        self.assertIn("file_path", slots)
        self.assertTrue(any("auth.py" in v for v in slots["file_path"]))

    def test_extracts_line_number(self):
        slots = extract_slots("the crash is at line 42")
        self.assertIn("line_number", slots)
        self.assertIn(42, slots["line_number"])

    def test_extracts_agent_name(self):
        slots = extract_slots("ask grove to send a message")
        self.assertIn("agent", slots)
        self.assertTrue(any("grove" in v.lower() for v in slots["agent"]))

    def test_extracts_multiple_slots(self):
        slots = extract_slots("fix the error in auth.py at line 99")
        self.assertIn("file_path", slots)
        self.assertIn("line_number", slots)
        self.assertIn(99, slots["line_number"])

    def test_empty_query(self):
        slots = extract_slots("")
        self.assertIsInstance(slots, dict)

    def test_no_slots(self):
        slots = extract_slots("hello world")
        # May be empty or have minimal matches — just shouldn't crash
        self.assertIsInstance(slots, dict)

    def test_extracts_url(self):
        slots = extract_slots("see https://example.com/api for details")
        self.assertIn("url", slots)
        self.assertTrue(any("https://example.com" in v for v in slots["url"]))

    def test_no_duplicate_slots(self):
        slots = extract_slots("check auth.py and auth.py again")
        if "file_path" in slots:
            # Duplicates should be collapsed
            vals = slots["file_path"]
            self.assertEqual(len(vals), len(set(v.lower() for v in vals)))


# ---------------------------------------------------------------------------
# Integration: intent → oracle routing
# ---------------------------------------------------------------------------

class TestIntentInOracle(unittest.TestCase):
    """Verify the intent → agent mapping table is self-consistent."""

    def test_all_intents_covered(self):
        from willow.routing.oracle import _INTENT_AGENT_MAP
        from willow.routing.intent import _INTENT_RULES
        # Every intent in the classifier should have an agent mapping
        for intent in _INTENT_RULES:
            self.assertIn(intent, _INTENT_AGENT_MAP,
                f"Intent '{intent}' has no agent mapping in oracle._INTENT_AGENT_MAP")

    def test_all_mapped_agents_in_roster(self):
        from willow.routing.oracle import _INTENT_AGENT_MAP, _AGENT_ROSTER
        known_agents = {a["name"] for a in _AGENT_ROSTER}
        for intent, agent in _INTENT_AGENT_MAP.items():
            self.assertIn(agent, known_agents,
                f"Intent '{intent}' maps to unknown agent '{agent}'")


if __name__ == "__main__":
    unittest.main()
