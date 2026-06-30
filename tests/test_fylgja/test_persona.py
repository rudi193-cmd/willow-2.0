"""Tests for willow.fylgja.persona."""
from willow.fylgja import persona as p


def test_render_picker_lists_all_personas():
    text = p.render_picker("")
    assert "PERSONA" in text
    assert "Hanuman" in text
    assert "Oakenscroll" in text
    assert "Jeles" in text


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


def test_persona_boot_overlay_path_oakenscroll():
    path = p.persona_boot_overlay_path("oakenscroll")
    assert path is not None
    assert path.name == "oakenscroll-boot.md"
    assert "Oakenscroll Boot Overlay" in path.read_text(encoding="utf-8")


def test_persona_boot_overlay_path_missing_persona():
    assert p.persona_boot_overlay_path("not-a-real-persona") is None
    assert p.persona_boot_overlay_path("none") is None


def test_boot_step7_documents_persona_overlay_convention():
    boot = (p._repo_root() / "willow/fylgja/skills/boot.md").read_text(encoding="utf-8")
    assert "{persona}-boot.md" in boot
    assert "skip silently" in boot
    assert "oakenscroll" not in boot.split("**7. Persona**")[1].split("**8.")[0]


def test_repo_persona_files_are_registered_and_have_boot_overlays():
    root = p._repo_root()
    persona_files = {
        path.stem
        for path in (root / "willow/fylgja/personas").glob("*.md")
        if path.name != "README.md"
    }
    personas, _persona_list = p.get_personas()
    assert persona_files <= set(personas)
    for name in sorted(persona_files):
        overlay = p.persona_boot_overlay_path(name)
        assert overlay is not None, name
        assert overlay.name == f"{name}-boot.md"


# --- Ada persona + per-project binding -------------------------------------

def test_ada_registered_at_slot_seven_without_shifting_others():
    # Existing numeric picks must not move (loki stays 3).
    assert p.parse_selection("3") == "loki"
    assert p.parse_selection("7") == "ada"
    personas, persona_list = p.get_personas()
    assert "ada" in personas
    assert persona_list.index("ada") == 6  # 0-based slot 7
    assert persona_list[-1] == "none"


def test_ada_is_not_a_fleet_named_persona():
    # Ada is a UTETY voice persona, not a fleet agent id — no collision guard.
    assert "ada" not in p._FLEET_NAMED_PERSONAS
    assert "loki" in p._FLEET_NAMED_PERSONAS


def test_ada_selection_never_blocked_by_collision_guard(monkeypatch):
    monkeypatch.setattr(p, "fleet_agent_id", lambda: "hanuman")
    monkeypatch.setenv("WILLOW_PERSONA_AGENT_BLOCK", "strict")
    allowed, msg = p.check_persona_fleet_collision("ada")
    assert allowed is True
    assert msg is None


def _bind_project(monkeypatch, tmp_path, project, persona):
    cfg = tmp_path / "project_personas.json"
    cfg.write_text(
        '{"version": 1, "bindings": {"%s": "%s"}}' % (project, persona),
        encoding="utf-8",
    )
    monkeypatch.setattr(p, "_project_personas_file", lambda: cfg)
    monkeypatch.setattr(p, "STATE_FILE", tmp_path / "active-persona")
    monkeypatch.setenv("WILLOW_HANDOFF_PROJECT", project)


def test_project_binding_makes_persona_active(tmp_path, monkeypatch):
    _bind_project(monkeypatch, tmp_path, "almanac-data", "ada")
    assert p.project_persona_binding() == "ada"
    assert p.active_persona() == "ada"  # no explicit pick yet → binding wins


def test_explicit_in_project_pick_overrides_binding(tmp_path, monkeypatch):
    _bind_project(monkeypatch, tmp_path, "almanac-data", "ada")
    monkeypatch.setenv("WILLOW_PERSONA_AGENT_BLOCK", "warn")
    monkeypatch.setattr(p, "fleet_agent_id", lambda: "willow")
    assert p.set_active_persona("loki") is True
    # Pick was made in this project → it sticks over the binding.
    assert p.active_persona() == "loki"


def test_binding_does_not_leak_to_unbound_project(tmp_path, monkeypatch):
    _bind_project(monkeypatch, tmp_path, "almanac-data", "ada")
    monkeypatch.setenv("WILLOW_PERSONA_AGENT_BLOCK", "warn")
    monkeypatch.setattr(p, "fleet_agent_id", lambda: "willow")
    # Explicit global pick made in a different project.
    monkeypatch.setenv("WILLOW_HANDOFF_PROJECT", "some-other-repo")
    assert p.set_active_persona("loki") is True
    assert p.active_persona() == "loki"
    # Switch into the bound project: binding wins (pick was elsewhere).
    monkeypatch.setenv("WILLOW_HANDOFF_PROJECT", "almanac-data")
    assert p.active_persona() == "ada"


def test_no_binding_falls_back_to_global_state(tmp_path, monkeypatch):
    _bind_project(monkeypatch, tmp_path, "almanac-data", "ada")
    monkeypatch.setenv("WILLOW_PERSONA_AGENT_BLOCK", "warn")
    monkeypatch.setattr(p, "fleet_agent_id", lambda: "willow")
    monkeypatch.setenv("WILLOW_HANDOFF_PROJECT", "unbound-repo")
    assert p.set_active_persona("skirnir") is True
    assert p.active_persona() == "skirnir"


def test_real_config_binds_almanac_repos_to_ada():
    binding = p._project_personas_file()
    assert binding.exists()
    import json
    data = json.loads(binding.read_text(encoding="utf-8"))
    assert data["bindings"]["almanac-data"] == "ada"
    assert data["bindings"]["almanac-data-dotgithub"] == "ada"
