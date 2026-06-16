"""tests/test_grove_p2p.py — unit tests for grove-p2p/1 chunk protocol."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO = Path(__file__).resolve().parent.parent
_GROVE_P2P_PATH = _REPO / "tools" / "grove_p2p.py"


def _load_grove_p2p_isolated():
    """Load grove_p2p with a mocked grove_db without clobbering core."""
    mock_db = types.ModuleType("core.grove_db")
    mock_db.BUS_BROADCAST = "__all__"
    mock_db.BUS_TYPES = frozenset(
        {"COMMAND", "RESPONSE", "EVENT", "INTERRUPT", "HEARTBEAT", "ACK", "DATA", "SYNC"}
    )

    saved = sys.modules.get("core.grove_db")
    sys.modules["core.grove_db"] = mock_db
    try:
        spec = importlib.util.spec_from_file_location(
            "grove_p2p_test_isolated", _GROVE_P2P_PATH
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, mock_db
    finally:
        if saved is not None:
            sys.modules["core.grove_db"] = saved
        else:
            sys.modules.pop("core.grove_db", None)


@pytest.fixture(scope="module")
def p2p():
    mod, mock_db = _load_grove_p2p_isolated()
    return mod, mock_db


# ── helpers ───────────────────────────────────────────────────────────────────

def test_sha256_roundtrip(p2p):
    mod, _ = p2p
    data = b"hello grove"
    assert mod._sha256(data) == hashlib.sha256(data).hexdigest()


def test_encode_decode_roundtrip(p2p):
    mod, _ = p2p
    data = b"\x00\x01\x02" * 1000
    assert mod._decode(mod._encode(data)) == data


def test_envelope_structure(p2p):
    mod, _ = p2p
    env = json.loads(mod._envelope("CHUNK", "abc123", index=0, total=5))
    assert env["protocol"] == "grove-p2p/1"
    assert env["type"] == "CHUNK"
    assert env["file_id"] == "abc123"
    assert env["index"] == 0
    assert env["total"] == 5


def test_unique_dest_no_collision(p2p, tmp_path):
    mod, _ = p2p
    dest = mod._unique_dest(tmp_path, "file.txt")
    assert dest == tmp_path / "file.txt"


def test_unique_dest_with_collision(p2p, tmp_path):
    mod, _ = p2p
    (tmp_path / "file.txt").write_bytes(b"x")
    dest = mod._unique_dest(tmp_path, "file.txt")
    assert dest == tmp_path / "file_1.txt"


def test_unique_dest_multiple_collisions(p2p, tmp_path):
    mod, _ = p2p
    (tmp_path / "file.txt").write_bytes(b"x")
    (tmp_path / "file_1.txt").write_bytes(b"x")
    dest = mod._unique_dest(tmp_path, "file.txt")
    assert dest == tmp_path / "file_2.txt"


# ── chunk math ───────────────────────────────────────────────────────────────

def test_chunk_count_exact(p2p):
    mod, _ = p2p
    data = b"x" * mod.CHUNK_SIZE
    total = (len(data) + mod.CHUNK_SIZE - 1) // mod.CHUNK_SIZE
    assert total == 1


def test_chunk_count_overflow(p2p):
    mod, _ = p2p
    data = b"x" * (mod.CHUNK_SIZE + 1)
    total = (len(data) + mod.CHUNK_SIZE - 1) // mod.CHUNK_SIZE
    assert total == 2


def test_chunk_count_zero_remainder(p2p):
    mod, _ = p2p
    data = b"x" * (mod.CHUNK_SIZE * 3)
    total = (len(data) + mod.CHUNK_SIZE - 1) // mod.CHUNK_SIZE
    assert total == 3


# ── reassembly ────────────────────────────────────────────────────────────────

def test_reassemble_produces_correct_hash(p2p, tmp_path):
    mod, mock_db = p2p
    data = b"the quick brown fox" * 500
    file_id = mod._sha256(data)
    chunks = {0: data[:100], 1: data[100:200], 2: data[200:]}
    t = {"meta": {"filename": "test.bin"}, "sender": "alice", "chunks": chunks, "total": 3}

    calls = []

    def fake_bus_send(conn, **kwargs):
        calls.append(kwargs)
        return {"id": 1}

    mock_db.bus_send = fake_bus_send

    mod._reassemble(MagicMock(), ch_id=1, agent="bob", file_id=file_id, t=t, out_dir=tmp_path)

    dest = tmp_path / "test.bin"
    assert dest.exists()
    assert dest.read_bytes() == data

    assert len(calls) == 1
    complete = json.loads(calls[0]["content"])
    assert complete["type"] == "COMPLETE"
    assert complete["verified"] is True
    assert complete["file_id"] == file_id


def test_reassemble_hash_mismatch_does_not_write(p2p, tmp_path):
    mod, mock_db = p2p
    data = b"correct data"
    bad_id = "0" * 64
    chunks = {0: data}
    t = {"meta": {"filename": "bad.bin"}, "sender": "alice", "chunks": chunks, "total": 1}

    mock_db.bus_send = MagicMock(return_value={"id": 1})

    mod._reassemble(MagicMock(), ch_id=1, agent="bob", file_id=bad_id, t=t, out_dir=tmp_path)

    assert not (tmp_path / "bad.bin").exists()

    complete = json.loads(mock_db.bus_send.call_args[1]["content"])
    assert complete["verified"] is False


# ── protocol constants ────────────────────────────────────────────────────────

def test_default_channel(p2p):
    mod, _ = p2p
    assert mod.CHANNEL_NAME == "grove-p2p"


def test_chunk_size_reasonable(p2p):
    mod, _ = p2p
    assert mod.CHUNK_SIZE <= 256 * 1024
    assert mod.CHUNK_SIZE >= 4 * 1024
