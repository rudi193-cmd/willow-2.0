"""Effect tests for core/intake.py atomic mark_promoted + locked writes.

These assert on real files after real operations — not on call shapes.
Guards the magma-layer class: a crash or race during the mark_promoted
rewrite must never truncate an intake JSONL or lose a promotion.
"""
import json
import threading

import pytest

from core import intake


@pytest.fixture()
def intake_root(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_INTAKE_ROOT", str(tmp_path))
    return tmp_path


def _read_records(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_write_then_mark_promoted_round_trip(intake_root):
    rid = intake.write("fact one", "test", "testagent")
    assert intake.mark_promoted("testagent", rid, "knowledge") is True

    files = list((intake_root / "testagent").glob("*.jsonl"))
    assert len(files) == 1
    recs = _read_records(files[0])
    assert len(recs) == 1
    assert recs[0]["id"] == rid
    assert recs[0]["promoted"] is True
    assert recs[0]["promote_tier"] == "knowledge"


def test_mark_promoted_preserves_other_records_and_junk_lines(intake_root):
    r1 = intake.write("fact one", "test", "testagent")
    r2 = intake.write("fact two", "test", "testagent")
    path = next((intake_root / "testagent").glob("*.jsonl"))
    # Simulate a historically corrupted line — it must survive the rewrite verbatim.
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("{not json at all\n")

    assert intake.mark_promoted("testagent", r1, "knowledge") is True

    lines = path.read_text().splitlines()
    assert "{not json at all" in lines
    parsed = []
    for line in lines:
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    by_id = {r["id"]: r for r in parsed}
    assert by_id[r1]["promoted"] is True
    assert by_id[r2]["promoted"] is False


def test_mark_promoted_missing_record_returns_false(intake_root):
    intake.write("fact one", "test", "testagent")
    assert intake.mark_promoted("testagent", "DOESNOTEXIST", "knowledge") is False


def test_no_temp_files_left_behind(intake_root):
    rid = intake.write("fact one", "test", "testagent")
    intake.mark_promoted("testagent", rid, "knowledge")
    leftovers = list((intake_root / "testagent").glob("*.tmp"))
    assert leftovers == []


def test_concurrent_promoters_lose_nothing(intake_root):
    """Two threads promoting different records in the same file: both must land.

    Before the _dir_lock + atomic-replace fix this was a lost-update race —
    the losing thread's rewrite clobbered the winner's promotion.
    """
    rids = [intake.write(f"fact {i}", "test", "testagent") for i in range(20)]

    def promote(rid):
        assert intake.mark_promoted("testagent", rid, "knowledge") is True

    threads = [threading.Thread(target=promote, args=(rid,)) for rid in rids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    path = next((intake_root / "testagent").glob("*.jsonl"))
    recs = _read_records(path)
    assert len(recs) == 20, "rewrite race dropped records"
    assert all(r["promoted"] is True for r in recs), "lost-update race dropped a promotion"


def test_concurrent_writes_do_not_interleave(intake_root):
    """Parallel intake.write calls: every record line must parse cleanly."""
    payload = "x" * 6000  # force each line well past PIPE_BUF

    def writer(i):
        intake.write(f"{i}:{payload}", "test", "testagent")

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    path = next((intake_root / "testagent").glob("*.jsonl"))
    recs = _read_records(path)  # raises JSONDecodeError on interleaved garbage
    assert len(recs) == 10
