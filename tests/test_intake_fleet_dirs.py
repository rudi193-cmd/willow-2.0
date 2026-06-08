from core.intake import ensure_fleet_intake_dirs


def test_ensure_fleet_intake_dirs_creates_agent_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_INTAKE_ROOT", str(tmp_path / "intake"))
    ensured = ensure_fleet_intake_dirs(["hanuman", "willow"])
    assert ensured == ["hanuman", "willow"]
    assert (tmp_path / "intake" / "hanuman").is_dir()
    assert (tmp_path / "intake" / "willow").is_dir()
