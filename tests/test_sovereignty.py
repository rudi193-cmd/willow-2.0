"""Tests for W19DS — Data Sovereignty: nuke + telemetry."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_telemetry_default_is_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    import importlib
    import root as seed
    importlib.reload(seed)
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path / "github" / ".willow"))
    wh = tmp_path / "github" / ".willow"
    wh.mkdir(parents=True, exist_ok=True)
    seed.step_telemetry_init()
    data = json.loads((wh / "telemetry.json").read_text())
    assert data["enabled"] is False


def test_telemetry_init_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    import importlib
    import root as seed
    importlib.reload(seed)
    wh = tmp_path / "github" / ".willow"
    wh.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WILLOW_HOME", str(wh))
    seed.step_telemetry_init()
    seed.step_telemetry_init()  # must not overwrite
    data = json.loads((wh / "telemetry.json").read_text())
    assert data["enabled"] is False


def test_willow_dir_has_telemetry_after_dirs(tmp_path, monkeypatch):
    monkeypatch.delenv("WILLOW_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    import importlib
    import root as seed
    importlib.reload(seed)
    seed.step_1_dirs()
    seed.step_telemetry_init()
    assert (tmp_path / "github" / ".willow" / "telemetry.json").exists()


def test_export_produces_json(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path / "store"))
    import importlib
    import core.willow_store as ws
    importlib.reload(ws)
    store = ws.WillowStore()
    store.put("test/atoms", {"_id": "exp1", "title": "exportable"})
    export_path = tmp_path / "export.json"
    data = {"store": {}}
    for col in store.collections():
        data["store"][col] = store.list(col)
    export_path.write_text(json.dumps(data, indent=2))
    loaded = json.loads(export_path.read_text())
    assert "store" in loaded
    assert "test/atoms" in loaded["store"]
