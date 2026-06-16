"""tests/test_grove_p2p.py — unit tests for grove-p2p/1 chunk protocol."""
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

# Patch grove_db before importing grove_p2p so no real DB connection is made
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import types
mock_db = types.ModuleType("core.grove_db")
mock_db.BUS_BROADCAST = "__all__"
mock_db.BUS_TYPES = frozenset({"COMMAND","RESPONSE","EVENT","INTERRUPT","HEARTBEAT","ACK","DATA","SYNC"})
sys.modules["core.grove_db"] = mock_db
sys.modules["core"] = types.ModuleType("core")
sys.modules["core"].grove_db = mock_db

from tools.grove_p2p import (
    _sha256, _encode, _decode, _envelope, _unique_dest,
    CHUNK_SIZE, CHANNEL_NAME,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def test_sha256_roundtrip():
    data = b"hello grove"
    assert _sha256(data) == hashlib.sha256(data).hexdigest()


def test_encode_decode_roundtrip():
    data = b"\x00\x01\x02" * 1000
    assert _decode(_encode(data)) == data


def test_envelope_structure():
    env = json.loads(_envelope("CHUNK", "abc123", index=0, total=5))
    assert env["protocol"] == "grove-p2p/1"
    assert env["type"] == "CHUNK"
    assert env["file_id"] == "abc123"
    assert env["index"] == 0
    assert env["total"] == 5


def test_unique_dest_no_collision(tmp_path):
    dest = _unique_dest(tmp_path, "file.txt")
    assert dest == tmp_path / "file.txt"


def test_unique_dest_with_collision(tmp_path):
    (tmp_path / "file.txt").write_bytes(b"x")
    dest = _unique_dest(tmp_path, "file.txt")
    assert dest == tmp_path / "file_1.txt"


def test_unique_dest_multiple_collisions(tmp_path):
    (tmp_path / "file.txt").write_bytes(b"x")
    (tmp_path / "file_1.txt").write_bytes(b"x")
    dest = _unique_dest(tmp_path, "file.txt")
    assert dest == tmp_path / "file_2.txt"


# ── chunk math ────────────────────────────────────────────────────────────────

def test_chunk_count_exact():
    data = b"x" * CHUNK_SIZE
    total = (len(data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    assert total == 1


def test_chunk_count_overflow():
    data = b"x" * (CHUNK_SIZE + 1)
    total = (len(data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    assert total == 2


def test_chunk_count_zero_remainder():
    data = b"x" * (CHUNK_SIZE * 3)
    total = (len(data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    assert total == 3


# ── reassembly ────────────────────────────────────────────────────────────────

def test_reassemble_produces_correct_hash(tmp_path):
    from tools.grove_p2p import _reassemble

    data    = b"the quick brown fox" * 500
    file_id = _sha256(data)
    chunks  = {0: data[:100], 1: data[100:200], 2: data[200:]}
    t       = {"meta": {"filename": "test.bin"}, "sender": "alice", "chunks": chunks, "total": 3}

    conn  = MagicMock()
    calls = []
    def fake_bus_send(conn, **kwargs):
        calls.append(kwargs)
        return {"id": 1}
    mock_db.bus_send = fake_bus_send

    _reassemble(conn, ch_id=1, agent="bob", file_id=file_id, t=t, out_dir=tmp_path)

    dest = tmp_path / "test.bin"
    assert dest.exists()
    assert dest.read_bytes() == data

    # COMPLETE message must be sent with verified=True
    assert len(calls) == 1
    complete = json.loads(calls[0]["content"])
    assert complete["type"] == "COMPLETE"
    assert complete["verified"] is True
    assert complete["file_id"] == file_id


def test_reassemble_hash_mismatch_does_not_write(tmp_path):
    from tools.grove_p2p import _reassemble

    data    = b"correct data"
    bad_id  = "0" * 64          # wrong file_id → hash mismatch
    chunks  = {0: data}
    t       = {"meta": {"filename": "bad.bin"}, "sender": "alice", "chunks": chunks, "total": 1}

    mock_db.bus_send = MagicMock(return_value={"id": 1})

    _reassemble(MagicMock(), ch_id=1, agent="bob", file_id=bad_id, t=t, out_dir=tmp_path)

    assert not (tmp_path / "bad.bin").exists()

    complete = json.loads(mock_db.bus_send.call_args[1]["content"])
    assert complete["verified"] is False


# ── protocol constants ────────────────────────────────────────────────────────

def test_default_channel():
    assert CHANNEL_NAME == "grove-p2p"


def test_chunk_size_reasonable():
    # Must fit in Postgres TEXT; base64 overhead is ~33%
    assert CHUNK_SIZE <= 256 * 1024
    assert CHUNK_SIZE >= 4 * 1024
