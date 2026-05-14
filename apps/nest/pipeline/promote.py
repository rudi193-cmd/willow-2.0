"""
pipeline/promote.py — Write a LOAM knowledge atom for a composted file.
b17: B2DA2  ΔΣ=42

Reads the compost summary from the files/store record and writes a KB atom
via willow_knowledge_ingest (called through the willow-1.9 PgBridge directly).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(os.environ.get(
    "WILLOW_19_ROOT",
    str(Path(__file__).parent.parent.parent / "willow-1.9")
)) / "core"))

from apps.nest.store_bridge import update_status, get_record

try:
    from pg_bridge import PgBridge
    _PG_OK = True
except ImportError:
    _PG_OK = False


def run(b17: str) -> dict:
    """
    Promote file to LOAM. Requires compost summary to be present in record.
    Returns the atom_id written, or error.
    """
    record = get_record(b17)
    if not record:
        return {"error": f"no record for b17={b17}"}

    summary = record.get("summary")
    if not summary:
        return {"error": f"no summary for b17={b17} — run compost first"}

    title = f"Nest: {record.get('filename', b17)} [{record.get('track', 'unknown')}]"
    path = record.get("moved_to") or record.get("path", "")

    if not _PG_OK:
        update_status(b17, "promoted", {"promote_note": "PgBridge unavailable — manual promote needed"})
        return {"b17": b17, "status": "promoted", "note": "PgBridge unavailable"}

    try:
        pg = PgBridge()
        atom_id = pg.ingest_knowledge(
            title=title,
            summary=summary,
            source_type="nest_file",
            domain="hanuman",
            source_path=path,
        )
        update_status(b17, "promoted", {"atom_id": atom_id})
        return {"b17": b17, "atom_id": atom_id, "status": "promoted"}
    except Exception as e:
        update_status(b17, "promoted", {"promote_error": str(e)})
        return {"b17": b17, "status": "promoted", "error": str(e)}
