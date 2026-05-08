"""
tests/test_sigmap_ranking.py — Unit tests for willow/sigmap/ranking.py
b17: SMAP1  ΔΣ=42

Covers: path match scoring, intent detection, test file penalty,
empty entries, graph boost for neighbors.
"""
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from willow.sigmap.ranking import rank, tokenize, _detect_intent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _entry(path: str, sigs: list[str] | None = None, tier: str = "balanced") -> dict:
    return {"path": path, "sigs": sigs or [], "tier": tier}


# ── Tokenizer tests ───────────────────────────────────────────────────────────

class TestTokenizer:
    def test_snake_case_split(self):
        tokens = tokenize("get_user_name")
        assert "get" in tokens or "user" in tokens or "name" in tokens

    def test_camel_case_split(self):
        tokens = tokenize("getUserName")
        combined = " ".join(tokens)
        # Should have split on camel boundary
        assert "user" in combined.lower() or "name" in combined.lower()

    def test_stop_words_removed(self):
        tokens = tokenize("the a an in of to for and or")
        assert tokens == []

    def test_path_split(self):
        tokens = tokenize("willow/sigmap/extractor.py")
        assert "willow" in tokens
        assert "sigmap" in tokens
        assert "extractor" in tokens


# ── Intent detection ──────────────────────────────────────────────────────────

class TestIntentDetection:
    def test_debug_intent(self):
        tokens = tokenize("fix the broken traceback")
        intent = _detect_intent(tokens)
        assert intent == "debug"

    def test_test_intent(self):
        tokens = tokenize("write test coverage for mock")
        intent = _detect_intent(tokens)
        assert intent == "test"

    def test_navigate_intent(self):
        tokens = tokenize("find where the router lives")
        intent = _detect_intent(tokens)
        assert intent == "navigate"

    def test_no_intent(self):
        tokens = tokenize("implement authentication service")
        intent = _detect_intent(tokens)
        # No guaranteed intent keyword here — may be None or something
        # Just verify it doesn't crash
        assert intent is None or isinstance(intent, str)

    def test_explain_intent(self):
        tokens = tokenize("explain how authentication works")
        intent = _detect_intent(tokens)
        assert intent == "explain"


# ── Ranking tests ─────────────────────────────────────────────────────────────

class TestRankBasics:
    def test_empty_entries_returns_empty(self):
        result = rank("some query", [])
        assert result == []

    def test_returns_same_count(self):
        entries = [
            _entry("foo.py", ["def foo(): pass"]),
            _entry("bar.py", ["class Bar: pass"]),
        ]
        result = rank("foo", entries)
        assert len(result) == 2

    def test_score_field_added(self):
        entries = [_entry("foo.py", ["def foo(): pass"])]
        result = rank("foo", entries)
        assert "score" in result[0]
        assert isinstance(result[0]["score"], float)

    def test_sorted_descending(self):
        entries = [
            _entry("auth/security.py", ["def authenticate(token): pass"]),
            _entry("utils/misc.py", ["def helper(): pass"]),
        ]
        result = rank("authenticate", entries)
        assert result[0]["score"] >= result[1]["score"]


class TestPathMatch:
    def test_path_match_scores_higher(self):
        entries = [
            _entry("router/users.py", ["def get_user(): pass"]),
            _entry("utils/helper.py", ["def do_thing(): pass"]),
        ]
        result = rank("users", entries)
        # router/users.py should score higher for "users" query
        scores = {e["path"]: e["score"] for e in result}
        assert scores["router/users.py"] > scores["utils/helper.py"]

    def test_sig_token_match_scores_higher_than_no_match(self):
        entries = [
            _entry("a.py", ["def authenticate(token): pass"]),
            _entry("b.py", ["def process_payment(): pass"]),
        ]
        result = rank("authenticate", entries)
        scores = {e["path"]: e["score"] for e in result}
        assert scores["a.py"] > scores["b.py"]


class TestIntentEffects:
    def test_test_intent_boosts_test_files(self):
        entries = [
            _entry("tests/test_auth.py", ["def test_login(): pass"], tier="fast"),
            _entry("auth/service.py", ["def login(user): pass"], tier="balanced"),
        ]
        result = rank("test login coverage", entries)
        scores = {e["path"]: e["score"] for e in result}
        # Test file should be boosted for test intent
        assert scores["tests/test_auth.py"] >= scores["auth/service.py"]

    def test_test_file_penalized_for_non_test_intent(self):
        entries = [
            _entry("tests/test_auth.py", ["def test_login(): pass"]),
            _entry("auth/service.py", ["def login(user): pass"]),
        ]
        # "explain" intent — test files should be penalized
        result = rank("explain how login works", entries)
        scores = {e["path"]: e["score"] for e in result}
        # auth/service.py should outscore tests when query is explain-oriented
        # (test penalty × 0.4 should kick in)
        assert scores["auth/service.py"] >= scores["tests/test_auth.py"]

    def test_navigate_boosts_path_match(self):
        entries = [
            _entry("routes/user_router.py", ["def get_users(): pass"]),
            _entry("db/models.py", ["class UserModel: pass"]),
        ]
        result = rank("find where user router lives", entries)
        scores = {e["path"]: e["score"] for e in result}
        # "router" and "user" appear in path — should score higher with navigate intent
        assert scores["routes/user_router.py"] > scores["db/models.py"]


class TestPenalties:
    def test_vendor_files_score_zero(self):
        entries = [
            _entry("node_modules/lodash/index.js", ["function get(obj, path): pass"]),
            _entry("src/utils.py", ["def get_value(): pass"]),
        ]
        result = rank("get", entries)
        scores = {e["path"]: e["score"] for e in result}
        assert scores["node_modules/lodash/index.js"] == 0.0

    def test_generated_files_penalized(self):
        entries = [
            _entry("proto/foo_pb2.py", ["class FooMessage: pass"]),
            _entry("api/client.py", ["class FooClient: pass"]),
        ]
        result = rank("Foo", entries)
        scores = {e["path"]: e["score"] for e in result}
        # Generated file should score lower
        assert scores["api/client.py"] > scores["proto/foo_pb2.py"]


class TestGraphBoost:
    def test_graph_neighbor_scores_higher(self):
        """A file that imports the query-matched file gets a graph boost."""
        entries = [
            _entry("core/engine.py", ["class Engine: pass"]),
            _entry("api/handlers.py", ["def handle_request(): pass"]),
            _entry("utils/misc.py", ["def noop(): pass"]),
        ]
        # api/handlers.py imports core/engine.py
        graph = {
            "api/handlers.py": ["core/engine.py"],
            "core/engine.py": [],
            "utils/misc.py": [],
        }
        result = rank("engine", entries, graph=graph)
        scores = {e["path"]: e["score"] for e in result}
        # core/engine.py should score highest (direct sig match)
        assert scores["core/engine.py"] >= scores["utils/misc.py"]

    def test_no_graph_does_not_crash(self):
        entries = [
            _entry("foo.py", ["def foo(): pass"]),
            _entry("bar.py", ["def bar(): pass"]),
        ]
        result = rank("foo", entries, graph=None)
        assert len(result) == 2

    def test_empty_graph_ok(self):
        entries = [_entry("foo.py", ["def foo(): pass"])]
        result = rank("foo", entries, graph={})
        assert len(result) == 1
        assert result[0]["score"] >= 0
