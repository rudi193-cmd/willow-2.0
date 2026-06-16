#!/usr/bin/env python3
"""
grove_p2p.py — P2P file transfer over the Grove bus.
b17: grove-p2p/1  ΔΣ=42

Protocol: grove-p2p/1
  ANNOUNCE  → sender broadcasts file metadata to recipient
  CHUNK     → sender pushes base64-encoded chunk (bus_type=DATA, message_type=file_share)
  ACK       → receiver confirms each chunk
  NACK      → receiver requests resend of a specific chunk
  COMPLETE  → receiver signals verified reassembly

Usage:
  python -m tools.grove_p2p send <file> --to <agent> [--sender <name>] [--channel grove-p2p]
  python -m tools.grove_p2p receive --agent <agent> [--out ~/Desktop/Nest] [--channel grove-p2p]
"""

import argparse
import base64
import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

from core import grove_db as db

CHUNK_SIZE    = 64 * 1024   # 64 KB — fits comfortably in Postgres TEXT
CHANNEL_NAME  = "grove-p2p"
POLL_INTERVAL = 0.5         # seconds between receive polls
SEND_TIMEOUT  = 300         # seconds to wait for COMPLETE


# ── helpers ──────────────────────────────────────────────────────────────────

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _encode(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _decode(s: str) -> bytes:
    return base64.b64decode(s)


def _envelope(type_: str, file_id: str, **kwargs) -> str:
    return json.dumps({"protocol": "grove-p2p/1", "type": type_, "file_id": file_id, **kwargs})


def _get_or_create_channel(conn, name: str) -> int:
    ch = next((c for c in db.list_channels(conn) if c["name"] == name), None)
    if ch:
        return ch["id"]
    return db.create_channel(conn, name=name, channel_type="group")["id"]


def _unique_dest(out_dir: Path, filename: str) -> Path:
    dest = out_dir / filename
    if not dest.exists():
        return dest
    stem, suffix = Path(filename).stem, Path(filename).suffix
    i = 1
    while dest.exists():
        dest = out_dir / f"{stem}_{i}{suffix}"
        i += 1
    return dest


# ── sender ───────────────────────────────────────────────────────────────────

def send(file_path: Path, to_agent: str, sender: str,
         channel: str = CHANNEL_NAME, chunk_size: int = CHUNK_SIZE) -> None:
    data     = file_path.read_bytes()
    file_id  = _sha256(data)
    total    = (len(data) + chunk_size - 1) // chunk_size

    print(f"[grove-p2p] {file_path.name} ({len(data):,} bytes, {total} chunks) → {to_agent}")

    conn = db.get_connection()
    try:
        ch_id = _get_or_create_channel(conn, channel)

        # ANNOUNCE
        db.bus_send(conn, channel_id=ch_id, sender=sender,
                    content=_envelope("ANNOUNCE", file_id,
                                      filename=file_path.name,
                                      size_bytes=len(data),
                                      chunk_size=chunk_size,
                                      chunk_count=total),
                    message_type="file_share", to_agent=to_agent,
                    bus_type="DATA", correlation_id=file_id[:16])

        # CHUNKS — background priority so normal messages aren't starved
        for i in range(total):
            chunk = data[i * chunk_size: (i + 1) * chunk_size]
            db.bus_send(conn, channel_id=ch_id, sender=sender,
                        content=_envelope("CHUNK", file_id,
                                          index=i, total=total,
                                          chunk_hash=_sha256(chunk),
                                          data=_encode(chunk)),
                        message_type="file_share", to_agent=to_agent,
                        bus_type="DATA", correlation_id=file_id[:16],
                        priority=5)
            if (i + 1) % 10 == 0 or i == total - 1:
                print(f"  {i + 1}/{total} chunks sent")

        print(f"[grove-p2p] all chunks sent — waiting for COMPLETE from {to_agent}")

        # Poll for COMPLETE or NACK
        cursor   = 0
        deadline = time.time() + SEND_TIMEOUT
        while time.time() < deadline:
            for m in db.bus_receive(conn, agent=sender, since_id=cursor):
                cursor = max(cursor, m["id"])
                try:
                    p = json.loads(m["content"])
                except (json.JSONDecodeError, KeyError):
                    continue
                if p.get("protocol") != "grove-p2p/1" or p.get("file_id") != file_id:
                    continue
                if p["type"] == "COMPLETE":
                    ok = p.get("verified", False)
                    print(f"[grove-p2p] COMPLETE — {'✓ verified' if ok else '✗ hash mismatch'}")
                    return
                if p["type"] == "NACK":
                    idx   = p["index"]
                    chunk = data[idx * chunk_size: (idx + 1) * chunk_size]
                    print(f"[grove-p2p] NACK chunk {idx} — resending")
                    db.bus_send(conn, channel_id=ch_id, sender=sender,
                                content=_envelope("CHUNK", file_id,
                                                  index=idx, total=total,
                                                  chunk_hash=_sha256(chunk),
                                                  data=_encode(chunk)),
                                message_type="file_share", to_agent=to_agent,
                                bus_type="DATA", correlation_id=file_id[:16],
                                priority=2)  # HIGH — resend is urgent
            time.sleep(POLL_INTERVAL)

        print("[grove-p2p] timeout waiting for COMPLETE", file=sys.stderr)
        sys.exit(1)
    finally:
        db.release_connection(conn)


# ── receiver ─────────────────────────────────────────────────────────────────

def receive(agent: str, out_dir: Path, channel: str = CHANNEL_NAME) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[grove-p2p] listening as {agent!r} on {channel!r} → {out_dir}")

    # in-flight: file_id → {meta, sender, chunks, total}
    transfers: dict[str, dict] = {}
    cursor = 0

    conn = db.get_connection()
    try:
        ch_id = _get_or_create_channel(conn, channel)
        while True:
            for m in db.bus_receive(conn, agent=agent, since_id=cursor):
                cursor = max(cursor, m["id"])
                if m.get("message_type") != "file_share":
                    continue
                try:
                    p = json.loads(m["content"])
                except (json.JSONDecodeError, KeyError):
                    continue
                if p.get("protocol") != "grove-p2p/1":
                    continue

                file_id = p["file_id"]
                sender  = m["sender"]

                if p["type"] == "ANNOUNCE":
                    transfers[file_id] = {
                        "meta": p, "sender": sender,
                        "chunks": {}, "total": p["chunk_count"],
                    }
                    print(f"[grove-p2p] ANNOUNCE {p['filename']} "
                          f"({p['size_bytes']:,} bytes, {p['chunk_count']} chunks) from {sender}")

                elif p["type"] == "CHUNK":
                    if file_id not in transfers:
                        # ANNOUNCE missed — reconstruct envelope from CHUNK
                        transfers[file_id] = {
                            "meta": {}, "sender": sender,
                            "chunks": {}, "total": p["total"],
                        }
                    t   = transfers[file_id]
                    idx = p["index"]
                    raw = _decode(p["data"])

                    if _sha256(raw) != p["chunk_hash"]:
                        print(f"[grove-p2p] chunk {idx} hash mismatch — NACK")
                        db.bus_send(conn, channel_id=ch_id, sender=agent,
                                    content=_envelope("NACK", file_id, index=idx),
                                    to_agent=t["sender"], bus_type="ACK",
                                    correlation_id=file_id[:16])
                    else:
                        t["chunks"][idx] = raw
                        db.bus_send(conn, channel_id=ch_id, sender=agent,
                                    content=_envelope("ACK", file_id, index=idx),
                                    to_agent=t["sender"], bus_type="ACK",
                                    correlation_id=file_id[:16], priority=3)

                    if len(t["chunks"]) == t["total"]:
                        _reassemble(conn, ch_id, agent, file_id, t, out_dir)
                        del transfers[file_id]

            time.sleep(POLL_INTERVAL)
    finally:
        db.release_connection(conn)


def _reassemble(conn, ch_id: int, agent: str, file_id: str,
                t: dict, out_dir: Path) -> None:
    data     = b"".join(t["chunks"][i] for i in range(t["total"]))
    verified = _sha256(data) == file_id
    filename = t["meta"].get("filename", file_id[:16])
    dest     = _unique_dest(out_dir, filename)

    if verified:
        dest.write_bytes(data)
        print(f"[grove-p2p] ✓ {filename} → {dest}")
    else:
        print(f"[grove-p2p] ✗ hash mismatch on reassembly — discarding", file=sys.stderr)

    db.bus_send(conn, channel_id=ch_id, sender=agent,
                content=_envelope("COMPLETE", file_id,
                                  verified=verified, final_hash=_sha256(data)),
                to_agent=t["sender"], bus_type="EVENT",
                correlation_id=file_id[:16])


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap  = argparse.ArgumentParser(description="Grove P2P file transfer (grove-p2p/1)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("send", help="send a file to another agent")
    sp.add_argument("file")
    sp.add_argument("--to",         required=True, help="recipient agent name")
    sp.add_argument("--sender",     default="hanuman")
    sp.add_argument("--channel",    default=CHANNEL_NAME)
    sp.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)

    rp = sub.add_parser("receive", help="receive files (runs until interrupted)")
    rp.add_argument("--agent",   required=True)
    rp.add_argument("--out",     default=str(Path.home() / "Desktop" / "Nest"))
    rp.add_argument("--channel", default=CHANNEL_NAME)

    args = ap.parse_args()
    if args.cmd == "send":
        send(Path(args.file), args.to, args.sender, args.channel, args.chunk_size)
    else:
        receive(args.agent, Path(args.out), args.channel)


if __name__ == "__main__":
    main()
