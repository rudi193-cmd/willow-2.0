"""Tests for the nest/v1 feedback edge (docs/NEST_FEEDBACK_SCHEMA.md).

Covers: prediction frozen at scan, outcome derivation from final dest,
confirm-vs-override event classification, the intake poisoning regression
(override must record the outcome track, not the prediction), the
corrections counter, and the rule-delta flag threshold.
"""

from pathlib import Path

import pytest

from sap.core import nest_intake


@pytest.fixture
def nest_env(tmp_path, monkeypatch):
    """Isolated drop zone, queue, and track destinations under tmp_path."""
    drop = tmp_path / "Nest"
    drop.mkdir()
    dests = {
        "journal": tmp_path / "personal" / "journal",
        "legal": tmp_path / "personal" / "legal",
        "screenshots": tmp_path / "personal" / "photos" / "screenshots",
    }
    monkeypatch.setattr(nest_intake, "NEST_DIRS", [drop])
    monkeypatch.setattr(nest_intake, "QUEUE_FILE", tmp_path / "nest-queue.json")
    monkeypatch.setattr(nest_intake, "TRACK_TO_DEST", dests)

    intake_writes = []

    def fake_intake_write(**kwargs):
        intake_writes.append(kwargs)
        return "TESTID"

    soil_store = {}

    class FakeSoil:
        @staticmethod
        def get(collection, record_id):
            return soil_store.get((collection, record_id))

        @staticmethod
        def put(collection, record_id, record):
            soil_store[(collection, record_id)] = record

    import core.intake
    import core.soil
    import core.agent_identity
    monkeypatch.setattr(core.intake, "write", fake_intake_write)
    monkeypatch.setattr(core.soil, "get", FakeSoil.get)
    monkeypatch.setattr(core.soil, "put", FakeSoil.put)
    monkeypatch.setattr(core.agent_identity, "require_agent_name", lambda: "testagent")

    return {
        "drop": drop,
        "dests": dests,
        "intake_writes": intake_writes,
        "soil": soil_store,
    }


def _stage(nest_env, filename: str) -> dict:
    (nest_env["drop"] / filename).write_text("x")
    staged = nest_intake.scan_nest()
    return next(i for i in staged if i["filename"] == filename)


def test_scan_freezes_prediction(nest_env):
    item = _stage(nest_env, "2026-07-06.md")
    pred = item["prediction"]
    assert pred["track"] == "journal"
    assert pred["method"] == "heuristic"
    assert pred["classifier_version"] == nest_intake.CLASSIFIER_VERSION
    assert pred["confidence"] > 0


def test_scan_unknown_prediction(nest_env):
    item = _stage(nest_env, "mystery.xyz")
    assert item["track"] == "unknown"
    assert item["prediction"]["method"] == "none"
    assert item["prediction"]["confidence"] == 0.0


def test_track_for_dest_reverse_map(nest_env):
    legal = nest_env["dests"]["legal"]
    assert nest_intake._track_for_dest(legal) == "legal"
    assert nest_intake._track_for_dest(legal / "sub") == "legal"
    assert nest_intake._track_for_dest(Path("/somewhere/else")) == "custom"


def test_confirm_matched_event(nest_env):
    item = _stage(nest_env, "2026-07-06.md")
    result = nest_intake.confirm_review(item["id"])
    assert result["event"] == "confirm"
    assert result["track"] == "journal"

    (rec,) = nest_env["intake_writes"]
    assert rec["source"] == "nest/confirm"
    extra = rec["extra"]
    assert extra["schema"] == "nest/v1"
    assert extra["outcome"]["matched"] is True
    # no correction recorded on a match
    assert not nest_env["soil"]


def test_override_records_outcome_not_prediction(nest_env):
    """Regression: pre-nest/v1 this wrote the WRONG predicted track as verified."""
    item = _stage(nest_env, "2026-07-06.md")  # predicted journal
    legal_dest = nest_env["dests"]["legal"] / "2026-07-06.md"
    result = nest_intake.confirm_review(item["id"], override_dest=str(legal_dest))
    assert result["event"] == "override"
    assert result["track"] == "legal"
    assert result["predicted_track"] == "journal"

    (rec,) = nest_env["intake_writes"]
    assert "legal" in rec["tags"]
    assert "journal" not in rec["tags"]
    assert rec["keywords"][0] == "legal"
    extra = rec["extra"]
    assert extra["prediction"]["track"] == "journal"
    assert extra["outcome"]["track"] == "legal"
    assert extra["outcome"]["matched"] is False


def test_override_increments_correction_counter(nest_env):
    for i in range(2):
        item = _stage(nest_env, f"2026-07-0{i + 1}.md")
        dest = nest_env["dests"]["legal"] / item["filename"]
        nest_intake.confirm_review(item["id"], override_dest=str(dest))

    corr = [v for (coll, _), v in nest_env["soil"].items()
            if coll == nest_intake.CORRECTIONS_COLLECTION]
    assert len(corr) == 1
    assert corr[0]["count"] == 2
    assert corr[0]["predicted_track"] == "journal"
    assert corr[0]["outcome_track"] == "legal"
    # below threshold — no flag yet
    assert not any(coll == "testagent/flags" for (coll, _) in nest_env["soil"])


def test_flag_opens_at_threshold(nest_env):
    for i in range(nest_intake.CORRECTION_FLAG_THRESHOLD):
        item = _stage(nest_env, f"2026-07-1{i}.md")
        dest = nest_env["dests"]["legal"] / item["filename"]
        nest_intake.confirm_review(item["id"], override_dest=str(dest))

    flags = [v for (coll, _), v in nest_env["soil"].items()
             if coll == "testagent/flags"]
    assert len(flags) == 1
    flag = flags[0]
    assert flag["flag_state"] == "open"
    assert flag["source"] == "nest_feedback"
    assert "journal" in flag["title"] and "legal" in flag["title"]
    assert "CLASSIFIER_VERSION" in flag["fix_path"]


def test_skip_writes_observed_record(nest_env):
    item = _stage(nest_env, "2026-07-06.md")
    nest_intake.skip_item(item["id"])

    (rec,) = nest_env["intake_writes"]
    assert rec["source"] == "nest/skip"
    assert rec["tier"] == "observed"
    assert rec["extra"]["event"] == "skip"
    assert rec["extra"]["outcome"]["matched"] is None


def test_legacy_queue_row_without_prediction(nest_env):
    """Rows staged before nest/v1 reconstruct a prediction from 'track'."""
    src = nest_env["drop"] / "old_item.md"
    src.write_text("x")
    queue = [{
        "id": 1, "src": str(src), "filename": "old_item.md",
        "track": "journal",
        "proposed_dest": str(nest_env["dests"]["journal"] / "old_item.md"),
        "status": "pending", "staged_at": "2026-07-01T00:00:00+00:00",
    }]
    nest_intake._save_queue(queue)

    result = nest_intake.confirm_review(1)
    assert result["event"] == "confirm"
    (rec,) = nest_env["intake_writes"]
    assert rec["extra"]["prediction"]["classifier_version"] == "pre-nest-v1"
