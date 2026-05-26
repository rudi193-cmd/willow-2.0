"""Tests for willow.fylgja.persona."""
from willow.fylgja import persona as p


def test_render_picker_lists_all_personas():
    text = p.render_picker("")
    assert "<persona-picker>" in text
    assert "Hanuman" in text
    assert "Oakenscroll" in text


def test_parse_selection_by_number():
    assert p.parse_selection("3") == "loki"


def test_parse_selection_by_name():
    assert p.parse_selection("hanuman") == "hanuman"
    assert p.parse_selection("switch to skirnir") == "skirnir"


def test_set_and_read_active_persona(tmp_path, monkeypatch):
    state = tmp_path / "active-persona"
    monkeypatch.setattr(p, "STATE_FILE", state)
    assert p.set_active_persona("loki")
    assert p.active_persona() == "loki"


def test_persona_path_points_at_repo_personas():
    path = p._persona_path("hanuman")
    assert path.endswith("willow/fylgja/personas/hanuman.md")
    assert p.PERSONAS["hanuman"]["path"] == path
