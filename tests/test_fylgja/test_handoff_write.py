"""Tests for canonical session handoff markdown writer."""
import re
from datetime import datetime, timezone

from willow.fylgja.handoff_write import next_session_filename, write_session_handoff


def test_next_session_filename_format():
    name = next_session_filename("hanuman", suffix="")
    assert name.startswith("session_handoff-")
    assert name.endswith("_hanuman.md")


def _patch_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "willow.fylgja.handoff_write.handoff_dir",
        lambda agent: tmp_path / agent,
    )
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def test_first_of_day_is_lettered(monkeypatch, tmp_path):
    """Never the bare base — a letterless name loses the recency suffix
    tiebreak to any lettered file from the same date (intake 640ECA8B)."""
    today = _patch_dir(monkeypatch, tmp_path)
    assert next_session_filename("hanuman") == f"session_handoff-{today}a_hanuman.md"


def test_skips_taken_letters(monkeypatch, tmp_path):
    today = _patch_dir(monkeypatch, tmp_path)
    dest = tmp_path / "hanuman"
    dest.mkdir(parents=True)
    for letter in ("a", "b"):
        (dest / f"session_handoff-{today}{letter}_hanuman.md").write_text("x")
    name = next_session_filename("hanuman")
    assert name == f"session_handoff-{today}c_hanuman.md"
    # letterless legacy file present must not be handed out either
    (dest / f"session_handoff-{today}_hanuman.md").write_text("x")
    assert next_session_filename("hanuman") == f"session_handoff-{today}c_hanuman.md"


def test_explicit_free_suffix_honored(monkeypatch, tmp_path):
    today = _patch_dir(monkeypatch, tmp_path)
    assert (
        next_session_filename("hanuman", suffix="k")
        == f"session_handoff-{today}k_hanuman.md"
    )


def test_explicit_out_of_order_suffix_bumped_past_max(monkeypatch, tmp_path):
    """A free but out-of-order explicit suffix (e.g. 'h' after 'j' already
    exists) must not be honored — it would lose the recency tiebreak in
    handoff_latest_sort_key, same as the letterless-base bug (flag
    flag-handoff-v3-explicit-suffix-ordering, session be24d8e6)."""
    today = _patch_dir(monkeypatch, tmp_path)
    dest = tmp_path / "hanuman"
    dest.mkdir(parents=True)
    (dest / f"session_handoff-{today}j_hanuman.md").write_text("x")
    assert (
        next_session_filename("hanuman", suffix="h")
        == f"session_handoff-{today}k_hanuman.md"
    )


def test_explicit_suffix_equal_to_max_falls_through(monkeypatch, tmp_path):
    today = _patch_dir(monkeypatch, tmp_path)
    dest = tmp_path / "hanuman"
    dest.mkdir(parents=True)
    (dest / f"session_handoff-{today}j_hanuman.md").write_text("x")
    assert (
        next_session_filename("hanuman", suffix="j")
        == f"session_handoff-{today}k_hanuman.md"
    )


def test_result_always_matches_lettered_pattern(monkeypatch, tmp_path):
    _patch_dir(monkeypatch, tmp_path)
    name = next_session_filename("hanuman")
    assert re.match(r"^session_handoff-\d{4}-\d{2}-\d{2}[a-z]_hanuman\.md$", name)


def test_write_session_handoff_adds_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "willow.fylgja.handoff_write.handoff_dir",
        lambda agent: tmp_path / agent,
    )
    path = write_session_handoff(
        "hanuman",
        "# SESSION HANDOFF — test\n\n## Open Threads\n- one\n",
        project="willow-2.0",
    )
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\nagent: hanuman\n")
    assert "## Open Threads" in text
