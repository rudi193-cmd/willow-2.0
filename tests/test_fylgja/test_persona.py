"""Tests for willow.fylgja.persona."""
from willow.fylgja import persona as p


def test_render_picker_lists_all_personas():
    text = p.render_picker("")
    assert "PERSONA" in text
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


def test_prompt_submit_block_first_turn_no_selection_emits_gate():
    # No persona keyword in prompt → gate fires, PERSONA-VISIBLE must NOT appear
    block = p.prompt_submit_block(is_first=True, prompt="good afternoon")
    assert "PERSONA-GATE" in block
    assert "PERSONA-VISIBLE" not in block


def test_prompt_submit_block_first_turn_with_selection_emits_visible(tmp_path, monkeypatch):
    # Selection in prompt → gate skips, PERSONA-VISIBLE instruction emitted
    state = tmp_path / "active-persona"
    monkeypatch.setattr(p, "STATE_FILE", state)
    monkeypatch.setattr(p, "fleet_agent_id", lambda: "hanuman")
    block = p.prompt_submit_block(is_first=True, prompt="hanuman")
    assert "PERSONA-VISIBLE" in block
    assert "Paste the PERSONA block" in block
    assert "PERSONA-GATE" not in block
    assert "PERSONA-IDENTITY" in block
    assert "Fleet identity remains **hanuman**" in block


def test_persona_identity_banner_on_switch(tmp_path, monkeypatch):
    state = tmp_path / "active-persona"
    monkeypatch.setattr(p, "STATE_FILE", state)
    monkeypatch.setattr(p, "fleet_agent_id", lambda: "hanuman")
    banner = p.persona_identity_banner("skirnir", switched=True)
    assert "Persona changed to" in banner
    assert "Fleet identity remains **hanuman**" in banner
    assert "./willow agents active" in banner


def test_fleet_named_persona_collision_warns_but_allows(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "fleet_agent_id", lambda: "hanuman")
    monkeypatch.setenv("WILLOW_PERSONA_AGENT_BLOCK", "warn")
    allowed, msg = p.check_persona_fleet_collision("loki")
    assert allowed is True
    assert msg and "loki" in msg and "hanuman" in msg


def test_fleet_named_persona_collision_strict_blocks(tmp_path, monkeypatch):
    state = tmp_path / "active-persona"
    monkeypatch.setattr(p, "STATE_FILE", state)
    monkeypatch.setattr(p, "fleet_agent_id", lambda: "hanuman")
    monkeypatch.setenv("WILLOW_PERSONA_AGENT_BLOCK", "strict")
    assert p.set_active_persona("loki") is False


def test_render_picker_shows_fleet_identity(monkeypatch):
    monkeypatch.setattr(p, "fleet_agent_id", lambda: "hanuman")
    text = p.render_picker("skirnir")
    assert "Fleet identity: **hanuman**" in text
