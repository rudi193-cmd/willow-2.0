import json
from unittest.mock import patch

from willow.fylgja import anchor_state as anchor
from willow.fylgja import session_inject as inject


def test_write_state_mirrors_to_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        anchor,
        "state_file",
        lambda agent: tmp_path / f"anchor_state_{agent}.json",
    )
    anchor.write_state("willow", {"prompt_count": 7})
    path = tmp_path / "anchor_state_willow.json"
    assert path.is_file()
    assert json.loads(path.read_text())["prompt_count"] == 7


def test_bump_prompt_count(tmp_path, monkeypatch):
    monkeypatch.setattr(
        anchor,
        "state_file",
        lambda agent: tmp_path / f"anchor_state_{agent}.json",
    )
    monkeypatch.setattr("core.soil.get", lambda *a, **k: None)
    assert anchor.bump_prompt_count("willow") == 1
    assert anchor.bump_prompt_count("willow") == 2
    assert anchor.prompt_count("willow") == 2


def test_context_status_thresholds():
    assert anchor.context_status(0) == "STATUS_OK"
    assert anchor.context_status(14) == "STATUS_OK"
    assert anchor.context_status(15) == "COMPACT_NOW"
    assert anchor.context_status(25) == "COMPACT_NOW"
    assert anchor.context_status(26) == "HANDOFF_NOW"


def test_should_skip_duplicate_within_ttl(tmp_path, monkeypatch):
    marker = tmp_path / "marker.json"
    monkeypatch.setattr(inject, "_MARKER", marker)
    fp = "abc123"
    inject.record_injection("sess-1", fp, lite=False)
    assert inject.should_skip_duplicate("sess-1", fp) is True
    assert inject.should_skip_duplicate("sess-2", fp) is False
    assert inject.should_skip_duplicate("sess-1", "other") is False


def test_continuation_source_detection():
    assert inject.is_continuation_source("compact") is True
    assert inject.is_continuation_source("resume") is True
    assert inject.is_fresh_source("startup") is True
    assert inject.is_fresh_source("clear") is True
