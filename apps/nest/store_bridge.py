"""
store_bridge.py — Willow SOIL store wrapper for Nest pipeline state.
b17: 1284BC7D  ΔΣ=42

Reads/writes file records in files/store as they move through pipeline stages.
Talks to Willow via SAP-gated SoilClient. No direct DB access.
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_WILLOW_ROOT = Path(os.environ.get("WILLOW_ROOT", Path(__file__).parent.parent.parent))
_SAP_PATH    = _WILLOW_ROOT / "sap" / "clients"
if _SAP_PATH.exists() and str(_WILLOW_ROOT) not in sys.path:
    sys.path.insert(0, str(_WILLOW_ROOT))

try:
    from sap.clients.soil_client import SoilClient
except ImportError:
    SoilClient = None  # type: ignore

APP_ID           = "willow-nest"
FILES_COLLECTION = "files/store"

_client: "SoilClient | None" = None


def _get_client() -> "SoilClient | None":
    global _client
    if _client is None and SoilClient is not None:
        _client = SoilClient(app_id=APP_ID)
    return _client


def gen_b17(length: int = 5) -> str:
    return uuid.uuid4().hex[:length].upper()


def write_file_record(
    b17: str,
    path: str,
    filename: str,
    track: str,
    status: str = "sorted",
    moved_to: "str | None" = None,
) -> str:
    client = _get_client()
    if not client:
        sys.stderr.write("[store_bridge] Willow unavailable — no-op\n")
        return b17
    record: dict = {
        "b17":        b17,
        "path":       path,
        "filename":   filename,
        "track":      track,
        "nest_status": status,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }
    if moved_to:
        record["moved_to"] = moved_to
    client.put(FILES_COLLECTION, record, record_id=b17)
    return b17


def update_status(b17: str, status: str, extra: "dict | None" = None) -> None:
    client = _get_client()
    if not client:
        sys.stderr.write("[store_bridge] Willow unavailable — update_status skipped\n")
        return
    existing = client.get(FILES_COLLECTION, b17)
    if not existing:
        raise KeyError(f"No files/store record for b17={b17}")
    existing["nest_status"] = status
    existing["updated_at"]  = datetime.now(timezone.utc).isoformat()
    if extra:
        existing.update(extra)
    client.put(FILES_COLLECTION, existing, record_id=b17)


def get_record(b17: str) -> "dict | None":
    client = _get_client()
    if not client:
        return None
    return client.get(FILES_COLLECTION, b17)
