"""
pipeline/archive.py — Move a file to cold storage and update its state.
b17: B2DA2  ΔΣ=42

Files >10MB go to /media/willow/archive/ (external drive).
All others go to ~/Ashokoa/Filed/archive/.
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.nest.store_bridge import update_status, get_record

ARCHIVE_LOCAL  = Path.home() / "personal" / "archive"
ARCHIVE_LARGE  = Path("/media/willow/archive")
SIZE_THRESHOLD = 10 * 1024 * 1024  # 10MB


def _unique_dest(dest_dir: Path, filename: str) -> Path:
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem, suffix = Path(filename).stem, Path(filename).suffix
    i = 1
    while dest.exists():
        dest = dest_dir / f"{stem}_{i}{suffix}"
        i += 1
    return dest


def run(b17: str) -> dict:
    """
    Move file to archive. Updates store record to 'archived'.
    """
    record = get_record(b17)
    if not record:
        return {"error": f"no record for b17={b17}"}

    src = Path(record.get("moved_to") or record.get("path", ""))
    if not src.exists():
        return {"error": f"file not found: {src}"}

    size = src.stat().st_size
    if size > SIZE_THRESHOLD and ARCHIVE_LARGE.exists():
        archive_dir = ARCHIVE_LARGE / record.get("track", "unknown")
    else:
        archive_dir = ARCHIVE_LOCAL / record.get("track", "unknown")

    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = _unique_dest(archive_dir, src.name)
    shutil.move(str(src), str(dest))

    update_status(b17, "archived", {
        "archived_to": str(dest),
        "archive_size_bytes": size,
    })

    return {
        "b17": b17,
        "archived_to": str(dest),
        "size_bytes": size,
        "status": "archived",
    }
