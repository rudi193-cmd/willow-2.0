"""corpus/confirmations capture — detect and store positive confirmation signals.

Verifies:
- detect_confirmation() matches positive approval statements
- detect_confirmation() excludes corrections, short prompts, and non-signals
- detect_confirmation() yields to detect_correction() when both could match
- upsert_confirmation() deduplicates by content
"""
import pytest
from willow.fylgja.confirmations import COLLECTION, confirmation_record_id, upsert_confirmation
from willow.fylgja.events.prompt_submit import detect_confirmation, detect_correction


class FakeStore:
    def __init__(self):
        self.data: dict[tuple[str, str], dict] = {}

    def get(self, collection, record_id):
        return self.data.get((collection, record_id))

    def put(self, collection, record, record_id=None):
        self.data[(collection, record_id or record["id"])] = dict(record)

    def all(self, collection):
        return [r for (c, _), r in self.data.items() if c == collection]


# --- detect_confirmation ---

@pytest.mark.parametrize("prompt", [
    "yes exactly",
    "yes that's right",
    "perfect",
    "good call",
    "that works",
    "right approach",
    "that's exactly what I wanted",
    "that's perfect",
])
def test_detect_confirmation_matches(prompt):
    assert detect_confirmation(prompt), f"Expected match: {prompt!r}"


@pytest.mark.parametrize("prompt", [
    "go",
    "ok",
    "",
    "don't do that again",
    "never use Bash for this",
    "stop writing summaries",
    "wrong approach, use the MCP tool",
    "I prefer you summarize first",
])
def test_detect_confirmation_excludes_corrections_and_short(prompt):
    assert not detect_confirmation(prompt), f"Expected no match: {prompt!r}"


@pytest.mark.parametrize("prompt", [
    "stop doing that, it is wrong",
    "never use Bash again for this",
])
def test_correction_takes_precedence_over_confirmation(prompt):
    assert detect_correction(prompt)
    assert not detect_confirmation(prompt)


# --- upsert_confirmation ---

def test_same_confirmation_reuses_one_record():
    store = FakeStore()
    for n in range(3):
        rid = upsert_confirmation(store, content="perfect", session_id=f"s{n}")
    rows = store.all(COLLECTION)
    assert len(rows) == 1
    assert rows[0]["count"] == 3
    assert rows[0]["id"] == rid
    assert rows[0]["session_id"] == "s2"
    assert rows[0]["last_seen"] >= rows[0]["created_at"]


def test_distinct_confirmations_get_distinct_records():
    store = FakeStore()
    upsert_confirmation(store, content="perfect", session_id="s")
    upsert_confirmation(store, content="good call", session_id="s")
    assert len(store.all(COLLECTION)) == 2


def test_record_id_is_deterministic():
    a = confirmation_record_id("perfect")
    assert a == confirmation_record_id("perfect")
    assert a != confirmation_record_id("good call")
    assert a.startswith("conf-")


def test_record_fields():
    store = FakeStore()
    upsert_confirmation(store, content="yes exactly", session_id="s1")
    rows = store.all(COLLECTION)
    assert len(rows) == 1
    r = rows[0]
    assert r["type"] == "confirmation"
    assert r["valence"] == "positive"
    assert r["source"] == "prompt_submit_hook"
    assert r["sandbox"] is True
    assert r["b17"] == "CRPS0"
    assert r["count"] == 1
