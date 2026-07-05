"""Tests for the upstream_steward pending-queue groom + soil.archive.

The queue fossilized once (188 records, none newer than the last scout run,
every veto_deadline expired) because nothing ever moved records out of
`upstream_steward/pending`. Worse, stale drafts stayed armed for
auto-post-ready. These tests assert real store effects — records actually
leave the source collection and actually land in the archive — not that a
groom call merely happened.
"""
from datetime import datetime, timedelta, timezone

import pytest

from agents.hanuman.bin.upstream_watcher import (
    _SOIL_PENDING,
    GROOM_DRAFT_GRACE_DAYS,
    GROOM_NOISE_DAYS,
    GROOM_TERMINAL_DAYS,
    GROOM_WATCH_DAYS,
    groom,
)
from agents.hanuman.bin.upstream_responder import AUTO_POST_STALE_DAYS
from core import soil

NOW = datetime(2026, 7, 5, 3, 0, 0, tzinfo=timezone.utc)
ARCHIVE = f"_archive/{NOW.strftime('%Y-%m-%d')}/{_SOIL_PENDING}"


@pytest.fixture(autouse=True)
def store_root(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path))
    return tmp_path


def _iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


def _seed(wid: str, **fields) -> str:
    record = {
        "work_id": wid,
        "repo": "example/repo",
        "title": wid,
        "kind": "pullrequest",
        **fields,
    }
    soil.put(_SOIL_PENDING, wid, record)
    return wid


def _pending_ids() -> set:
    return {r.get("work_id") for r in soil.all_records(_SOIL_PENDING)}


def _archived_ids() -> set:
    return {r.get("work_id") for r in soil.all_records(ARCHIVE)}


# ── soil.archive / soil.delete primitives ────────────────────────────────────

def test_archive_moves_record_to_dated_collection():
    soil.put("some/queue", "r1", {"work_id": "r1", "payload": 42})
    dest = soil.archive("some/queue", "r1", date="2026-07-05")

    assert dest == "_archive/2026-07-05/some/queue"
    assert soil.get("some/queue", "r1") is None
    archived = soil.get(dest, "r1")
    assert archived is not None
    assert archived["payload"] == 42


def test_archive_missing_record_returns_none():
    assert soil.archive("some/queue", "does-not-exist") is None


def test_delete_removes_record():
    soil.put("some/queue", "r2", {"work_id": "r2"})
    assert soil.delete("some/queue", "r2") is True
    assert soil.get("some/queue", "r2") is None


# ── groom: terminal records ──────────────────────────────────────────────────

def test_old_terminal_records_are_archived():
    _seed("posted-old", status="posted", lane="draft",
          posted_at=_iso(GROOM_TERMINAL_DAYS + 1), created_at=_iso(30))
    _seed("skipped-old", status="skipped", lane="urgent",
          skipped_at=_iso(GROOM_TERMINAL_DAYS + 1), created_at=_iso(30))

    counts = groom(now=NOW)

    assert counts["terminal"] == 2
    assert _pending_ids() == set()
    assert _archived_ids() == {"posted-old", "skipped-old"}


def test_recent_terminal_records_stay_visible():
    _seed("posted-fresh", status="posted", lane="draft",
          posted_at=_iso(1), created_at=_iso(3))

    counts = groom(now=NOW)

    assert counts["terminal"] == 0
    assert _pending_ids() == {"posted-fresh"}


# ── groom: noise ─────────────────────────────────────────────────────────────

def test_noise_past_veto_deadline_is_archived():
    _seed("noise-old", status="noise", lane="noise",
          created_at=_iso(3), veto_deadline=_iso(1))

    counts = groom(now=NOW)

    assert counts["noise"] == 1
    assert _archived_ids() == {"noise-old"}


def test_noise_without_deadline_ages_out_on_created_at():
    # Early scout records (pre-2026-05-30) carry no veto_deadline at all.
    _seed("noise-legacy", status="noise", lane="noise",
          created_at=_iso(GROOM_NOISE_DAYS + 1))

    counts = groom(now=NOW)

    assert counts["noise"] == 1
    assert _pending_ids() == set()


def test_fresh_noise_is_kept():
    _seed("noise-fresh", status="noise", lane="noise",
          created_at=_iso(0.5), veto_deadline=_iso(-1.5))  # deadline in the future

    counts = groom(now=NOW)

    assert counts["noise"] == 0
    assert _pending_ids() == {"noise-fresh"}


# ── groom: watch ─────────────────────────────────────────────────────────────

def test_stale_watch_snapshot_is_archived():
    _seed("watch-old", status="watch", lane="watch",
          created_at=_iso(30), updated_at=_iso(GROOM_WATCH_DAYS + 1))

    counts = groom(now=NOW)

    assert counts["watch"] == 1
    assert _archived_ids() == {"watch-old"}


def test_active_watch_snapshot_is_kept():
    _seed("watch-live", status="watch", lane="watch",
          created_at=_iso(30), updated_at=_iso(2))

    counts = groom(now=NOW)

    assert counts["watch"] == 0
    assert _pending_ids() == {"watch-live"}


# ── groom: draft expiry (the auto-post disarm) ───────────────────────────────

def test_draft_far_past_veto_deadline_expires_and_archives():
    _seed("draft-fossil", status="awaiting_human", lane="draft",
          created_at=_iso(30), veto_deadline=_iso(GROOM_DRAFT_GRACE_DAYS + 1),
          draft_body="a month-old reply that must never post")

    counts = groom(now=NOW)

    assert counts["expired"] == 1
    assert _pending_ids() == set()
    archived = soil.get(ARCHIVE, "draft-fossil")
    assert archived["status"] == "expired"
    assert archived["expired_at"] == NOW.isoformat()
    # The original draft text survives in the archive for the record.
    assert "must never post" in archived["draft_body"]


def test_draft_inside_grace_window_is_untouched():
    # Past deadline but within grace: still legitimately auto-postable.
    _seed("draft-live", status="awaiting_human", lane="urgent",
          created_at=_iso(3), veto_deadline=_iso(1),
          draft_body="fresh reply")

    counts = groom(now=NOW)

    assert counts["expired"] == 0
    record = soil.get(_SOIL_PENDING, "draft-live")
    assert record["status"] == "awaiting_human"


def test_draft_without_deadline_is_never_expired():
    _seed("draft-no-deadline", status="awaiting_human", lane="draft",
          created_at=_iso(40), draft_body="x")

    counts = groom(now=NOW)

    assert counts["expired"] == 0
    assert _pending_ids() == {"draft-no-deadline"}


# ── groom + responder constants agree ────────────────────────────────────────

def test_grace_windows_are_consistent():
    # The responder withholds what the groom expires; if these drift apart a
    # gap opens where a stale draft is neither postable nor expired (fine) or
    # both postable and expired (not fine). Keep them equal.
    assert AUTO_POST_STALE_DAYS == GROOM_DRAFT_GRACE_DAYS


# ── legacy raw-id rows (2026-06-12 migration) ────────────────────────────────
#
# The layout-unification migration copied row ids verbatim — including ':'
# which _sanitize_id strips. The first live groom run reported 188 archived
# while all 188 remained: get/delete sanitized the lookup key and never
# matched the raw ids. These tests seed rows exactly as the migration left
# them and assert the store can actually touch them.

import sqlite3  # noqa: E402


def _make_legacy(collection: str, raw_id: str, record: dict) -> None:
    """Seed a row whose db id keeps characters _sanitize_id strips."""
    placeholder = "legacy-placeholder"
    soil.put(collection, placeholder, record)
    conn = sqlite3.connect(str(soil._db(collection)))
    conn.execute("UPDATE records SET id = ? WHERE id = ?", (raw_id, placeholder))
    conn.commit()
    conn.close()


def test_legacy_raw_id_is_gettable():
    _make_legacy("some/queue", "b17:LEG-1", {"work_id": "b17:LEG-1", "payload": 7})
    record = soil.get("some/queue", "b17:LEG-1")
    assert record is not None
    assert record["payload"] == 7


def test_legacy_raw_id_is_deletable():
    _make_legacy("some/queue", "b17:LEG-2", {"work_id": "b17:LEG-2"})
    assert soil.delete("some/queue", "b17:LEG-2") is True
    assert soil.get("some/queue", "b17:LEG-2") is None
    assert soil.all_records("some/queue") == []


def test_update_legacy_row_does_not_fork_sanitized_twin():
    _make_legacy("some/queue", "b17:LEG-3", {"work_id": "b17:LEG-3", "n": 1})
    soil._get_store().update("some/queue", "b17:LEG-3", {"n": 2})
    records = soil.all_records("some/queue")
    assert len(records) == 1
    assert records[0]["n"] == 2


def test_groom_archives_legacy_raw_id_records():
    _make_legacy(_SOIL_PENDING, "b17:UPST1-noise-1", {
        "work_id": "b17:UPST1-noise-1", "status": "noise", "lane": "noise",
        "created_at": _iso(20), "veto_deadline": _iso(18),
    })
    _make_legacy(_SOIL_PENDING, "b17:UPST1-draft-1", {
        "work_id": "b17:UPST1-draft-1", "status": "awaiting_human",
        "lane": "draft", "created_at": _iso(20), "veto_deadline": _iso(18),
        "draft_body": "fossil",
    })

    counts = groom(now=NOW)

    assert counts == {"terminal": 0, "noise": 1, "watch": 0,
                      "expired": 1, "failed": 0}
    assert _pending_ids() == set()
    expired = soil.get(ARCHIVE, "b17:UPST1-draft-1")
    assert expired["status"] == "expired"
