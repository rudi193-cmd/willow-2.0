"""tests/test_gate_pgp.py — PGP fingerprint resolution for manifest gate."""
import importlib
import json
import os
from pathlib import Path


def test_empty_pgp_env_uses_canonical_fingerprint(monkeypatch):
    monkeypatch.setenv("WILLOW_SAFE_ROOT", os.path.expanduser("~/github/SAFE/Applications"))
    monkeypatch.setenv("WILLOW_PGP_FINGERPRINT", "")
    import sap.core.gate as gate
    importlib.reload(gate)
    assert gate._EXPECTED_FP == gate._CANONICAL_PGP_FP
    assert gate._EXPECTED_FP == "9B6F87BEB4AE56E23D3D055724AED1D0216053F5"


def _seed_hanuman_manifest(agents_root: Path) -> None:
    hanuman = agents_root / "hanuman"
    hanuman.mkdir(parents=True, exist_ok=True)
    (hanuman / "safe-app-manifest.json").write_text(
        json.dumps(
            {
                "app_id": "hanuman",
                "permissions": ["postgres_read"],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_hanuman_may_call_fleet_identity_status(tmp_path, monkeypatch):
    apps = tmp_path / "apps"
    agents = tmp_path / "agents"
    apps.mkdir()
    _seed_hanuman_manifest(agents)
    monkeypatch.setenv("WILLOW_SAFE_ROOT", str(apps))
    monkeypatch.setenv("WILLOW_AGENTS_ROOT", str(agents))
    import sap.core.gate as gate

    importlib.reload(gate)
    assert gate.permitted("hanuman", "fleet_identity_status")


def test_hanuman_may_call_willow_attention(tmp_path, monkeypatch):
    apps = tmp_path / "apps"
    agents = tmp_path / "agents"
    apps.mkdir()
    _seed_hanuman_manifest(agents)
    monkeypatch.setenv("WILLOW_SAFE_ROOT", str(apps))
    monkeypatch.setenv("WILLOW_AGENTS_ROOT", str(agents))
    import sap.core.gate as gate

    importlib.reload(gate)
    assert gate.permitted("hanuman", "willow_attention")
