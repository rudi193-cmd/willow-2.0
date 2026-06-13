"""corpus/corrections dedupe — one record per unique (source, content).

Regression: uuid-keyed hook writes grew the collection to 768 rows
(158 duplicates of one sentence) by 2026-06-12.
"""
from willow.fylgja.corrections import COLLECTION, correction_record_id, upsert_correction


class FakeStore:
    def __init__(self):
        self.data: dict[tuple[str, str], dict] = {}

    def get(self, collection, record_id):
        return self.data.get((collection, record_id))

    def put(self, collection, record, record_id=None):
        self.data[(collection, record_id or record["id"])] = dict(record)

    def all(self, collection):
        return [r for (c, _), r in self.data.items() if c == collection]

    def delete(self, collection, record_id):
        return self.data.pop((collection, record_id), None) is not None


def test_same_block_reuses_one_record():
    store = FakeStore()
    for n in range(5):
        rid = upsert_correction(
            store, source="pre_tool_block",
            content="Blocked Bash: Use Glob for file listings",
            session_id=f"s{n}",
        )
    rows = store.all(COLLECTION)
    assert len(rows) == 1
    assert rows[0]["count"] == 5
    assert rows[0]["id"] == rid
    assert rows[0]["session_id"] == "s4"
    assert rows[0]["last_seen"] >= rows[0]["created_at"]


def test_distinct_content_gets_distinct_records():
    store = FakeStore()
    upsert_correction(store, source="pre_tool_block", content="Blocked Bash: A", session_id="s")
    upsert_correction(store, source="pre_tool_block", content="Blocked Bash: B", session_id="s")
    upsert_correction(store, source="prompt_submit_hook", content="Blocked Bash: A", session_id="s")
    assert len(store.all(COLLECTION)) == 3


def test_record_id_is_deterministic():
    a = correction_record_id("pre_tool_block", "x")
    assert a == correction_record_id("pre_tool_block", "x")
    assert a != correction_record_id("prompt_submit_hook", "x")
    assert a.startswith("corr-")


def test_prune_merges_and_archives():
    from scripts.prune_corrections import ARCHIVE, apply_plan, plan

    store = FakeStore()
    for n in range(4):
        store.put(COLLECTION, {
            "id": f"corr-old{n}", "source": "pre_tool_block",
            "content": "Blocked Bash: dup", "created_at": f"2026-06-0{n+1}",
        }, record_id=f"corr-old{n}")
    store.put(COLLECTION, {
        "id": "feedback_no_direct_db", "source": "feedback_no_direct_db.md",
        "content": "Never psql directly", "created_at": "2026-05-01",
    }, record_id="feedback_no_direct_db")

    groups, untouched = plan(store)
    assert len(groups) == 1
    assert len(untouched) == 1

    merged, archived = apply_plan(store, groups)
    assert (merged, archived) == (1, 4)
    rows = store.all(COLLECTION)
    assert len(rows) == 2  # canonical + curated
    canonical = next(r for r in rows if r["source"] == "pre_tool_block")
    assert canonical["count"] == 4
    assert canonical["created_at"] == "2026-06-01"
    assert canonical["last_seen"] == "2026-06-04"
    assert len(store.all(ARCHIVE)) == 4
