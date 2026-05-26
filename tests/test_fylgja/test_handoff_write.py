"""Tests for canonical session handoff markdown writer."""
from willow.fylgja.handoff_write import next_session_filename, write_session_handoff


def test_next_session_filename_format():
    name = next_session_filename("hanuman", suffix="")
    assert name.startswith("session_handoff-")
    assert name.endswith("_hanuman.md")


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
