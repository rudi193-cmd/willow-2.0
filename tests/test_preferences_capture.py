"""corpus/preferences capture — detect and store preference statements.

Mirrors test_corrections_dedupe.py. Verifies:
- detect_preference() matches positive preference statements
- detect_preference() excludes corrections and short prompts
- upsert_preference() deduplicates by content
"""
import pytest
from willow.fylgja.preferences import COLLECTION, preference_record_id, upsert_preference
from willow.fylgja.events.prompt_submit import detect_correction, detect_preference


class FakeStore:
    def __init__(self):
        self.data: dict[tuple[str, str], dict] = {}

    def get(self, collection, record_id):
        return self.data.get((collection, record_id))

    def put(self, collection, record, record_id=None):
        self.data[(collection, record_id or record["id"])] = dict(record)

    def all(self, collection):
        return [r for (c, _), r in self.data.items() if c == collection]


# --- detect_preference ---

@pytest.mark.parametrize("prompt", [
    "I prefer you write the handoff before closing the session",
    "I'd like you to confirm before pushing",
    "can you please keep doing that going forward",
    "I would rather you use the MCP tool here",
    "I'd appreciate it when you summarize the open threads",
    "from now on, please summarize the open threads",
    "going forward, can you include the branch name",
])
def test_detect_preference_matches(prompt):
    assert detect_preference(prompt), f"Expected match: {prompt!r}"


@pytest.mark.parametrize("prompt", [
    "short",
    "don't do that again",
    "never use Bash for this",
    "stop writing summaries",
    "wrong approach",
    "you missed the flag",
])
def test_detect_preference_excludes_corrections_and_short(prompt):
    assert not detect_preference(prompt), f"Expected no match: {prompt!r}"


@pytest.mark.parametrize("prompt", [
    "always do the handoff before we end",
    "please always do a handoff at the end",
    "from now on, can you always run tests first",
])
def test_correction_takes_precedence_over_preference(prompt):
    # "always do/run" matches correction patterns — captured as correction, not preference
    assert detect_correction(prompt)
    assert not detect_preference(prompt)


# --- upsert_preference ---

def test_same_preference_reuses_one_record():
    store = FakeStore()
    for n in range(4):
        rid = upsert_preference(
            store,
            content="I prefer you always run tests before pushing",
            session_id=f"s{n}",
        )
    rows = store.all(COLLECTION)
    assert len(rows) == 1
    assert rows[0]["count"] == 4
    assert rows[0]["id"] == rid
    assert rows[0]["session_id"] == "s3"
    assert rows[0]["last_seen"] >= rows[0]["created_at"]


def test_distinct_preferences_get_distinct_records():
    store = FakeStore()
    upsert_preference(store, content="I prefer A", session_id="s")
    upsert_preference(store, content="I prefer B", session_id="s")
    assert len(store.all(COLLECTION)) == 2


def test_record_id_is_deterministic():
    a = preference_record_id("I prefer short responses")
    assert a == preference_record_id("I prefer short responses")
    assert a != preference_record_id("I prefer long responses")
    assert a.startswith("pref-")


def test_record_fields():
    store = FakeStore()
    upsert_preference(store, content="I prefer you summarize", session_id="s1")
    rows = store.all(COLLECTION)
    assert len(rows) == 1
    r = rows[0]
    assert r["type"] == "preference"
    assert r["source"] == "prompt_submit_hook"
    assert r["sandbox"] is True
    assert r["b17"] == "CRPS0"
    assert r["count"] == 1
