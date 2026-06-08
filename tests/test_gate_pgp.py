"""tests/test_gate_pgp.py — PGP fingerprint resolution for manifest gate."""
import importlib
import os


def test_empty_pgp_env_uses_canonical_fingerprint(monkeypatch):
    monkeypatch.setenv("WILLOW_SAFE_ROOT", os.path.expanduser("~/github/SAFE/Applications"))
    monkeypatch.setenv("WILLOW_PGP_FINGERPRINT", "")
    import sap.core.gate as gate
    importlib.reload(gate)
    assert gate._EXPECTED_FP == gate._CANONICAL_PGP_FP
    assert gate._EXPECTED_FP == "9B6F87BEB4AE56E23D3D055724AED1D0216053F5"


def test_hanuman_may_call_fleet_identity_status():
    from sap.core.gate import permitted
    assert permitted("hanuman", "fleet_identity_status")


def test_hanuman_may_call_willow_attention():
    from sap.core.gate import permitted
    assert permitted("hanuman", "willow_attention")
