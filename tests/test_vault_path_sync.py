"""Guard the credential-vault writer/reader path invariant.

seed.py and shoot.py *write* credentials; sap/core/inference.load_credential
*reads* them. They previously drifted to different files (root vault.db vs
secrets/.willow_creds.db), so the MCP server silently fell back to plaintext.
These tests pin all three to the same canonical location and prove a
writer -> reader round-trip.
"""
from pathlib import Path


def _canonical(home: Path) -> Path:
    return home / "secrets" / ".willow_creds.db"


def test_writer_reader_paths_agree(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    import seed
    import shoot
    from sap.core import inference

    reader_db = inference._secrets_dir() / ".willow_creds.db"
    assert seed._vault_paths()[1] == reader_db == shoot._vault_paths()[1]
    assert str(reader_db) == str(_canonical(tmp_path))


def test_seed_write_then_reader_reads(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    import seed
    from sap.core import inference

    assert seed._vault_init()
    assert seed._vault_write("TEST_KEY", "TEST_KEY", "value-123")
    assert inference.load_credential("TEST_KEY") == "value-123"
    # the old, wrong locations must not be created
    assert not (tmp_path / "vault.db").exists()
    assert not (tmp_path / ".master.key").exists()


def test_shoot_write_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    import shoot
    from sap.core import inference

    assert shoot._vault_init()
    assert shoot._vault_write("TEST_KEY2", "TEST_KEY2", "value-456")
    assert shoot._vault_has_key("TEST_KEY2")
    assert inference.load_credential("TEST_KEY2") == "value-456"
