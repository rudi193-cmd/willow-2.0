"""corpus/scope_redirects capture — detect and store direction-change signals.

Verifies:
- detect_scope_redirect() matches mid-task direction changes
- detect_scope_redirect() excludes corrections, short prompts, and non-signals
- Corrections take precedence over scope redirects
- upsert_scope_redirect() deduplicates by content
"""
import pytest
from willow.fylgja.scope_redirects import COLLECTION, scope_redirect_record_id, upsert_scope_redirect
from willow.fylgja.events.prompt_submit import detect_scope_redirect, detect_correction


class FakeStore:
    def __init__(self):
        self.data: dict[tuple[str, str], dict] = {}

    def get(self, collection, record_id):
        return self.data.get((collection, record_id))

    def put(self, collection, record, record_id=None):
        self.data[(collection, record_id or record["id"])] = dict(record)

    def all(self, collection):
        return [r for (c, _), r in self.data.items() if c == collection]


# --- detect_scope_redirect ---

@pytest.mark.parametrize("prompt", [
    "actually let's skip that approach",
    "let's skip this for now",
    "not right now please",
    "skip that for now",
    "let's work on something else entirely",
    "let's look at something else here",
    "set that aside for now",
    "let's park that for later",
    "let's leave that for now",
])
def test_detect_scope_redirect_matches(prompt):
    assert detect_scope_redirect(prompt), f"Expected match: {prompt!r}"


@pytest.mark.parametrize("prompt", [
    "go",
    "ok let's",
    "",
    "I prefer you summarize first",
    "yes exactly that works",
    "perfect",
    "good call",
    "actually don't do that",  # caught as correction first
    "let's not focus on that",  # "not...that" matches correction pattern
])
def test_detect_scope_redirect_excludes_non_redirects(prompt):
    assert not detect_scope_redirect(prompt), f"Expected no match: {prompt!r}"


@pytest.mark.parametrize("prompt", [
    "never use Bash for that again",
    "stop using Bash for this",
])
def test_correction_takes_precedence_over_scope_redirect(prompt):
    assert detect_correction(prompt)
    assert not detect_scope_redirect(prompt)


# --- upsert_scope_redirect ---

def test_same_redirect_reuses_one_record():
    store = FakeStore()
    content = "let's skip this for now"
    for n in range(3):
        rid = upsert_scope_redirect(store, content=content, session_id=f"s{n}")
    rows = store.all(COLLECTION)
    assert len(rows) == 1
    assert rows[0]["count"] == 3
    assert rows[0]["session_id"] == "s2"
    assert rows[0]["last_seen"] >= rows[0]["created_at"]


def test_distinct_redirects_get_distinct_records():
    store = FakeStore()
    upsert_scope_redirect(store, content="let's skip this for now", session_id="s")
    upsert_scope_redirect(store, content="set that aside for now", session_id="s")
    assert len(store.all(COLLECTION)) == 2


def test_record_id_is_deterministic():
    a = scope_redirect_record_id("forget that")
    assert a == scope_redirect_record_id("forget that")
    assert a != scope_redirect_record_id("skip that for now")
    assert a.startswith("redir-")


def test_record_fields():
    store = FakeStore()
    upsert_scope_redirect(store, content="let's move on", session_id="s1")
    rows = store.all(COLLECTION)
    assert len(rows) == 1
    r = rows[0]
    assert r["type"] == "scope_redirect"
    assert r["valence"] == "negative"
    assert r["source"] == "prompt_submit_hook"
    assert r["sandbox"] is True
    assert r["b17"] == "CRPS0"
    assert r["count"] == 1
