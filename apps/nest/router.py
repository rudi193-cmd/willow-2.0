"""
router.py — Intake router for the Nest pipeline.
b17: 1284BC7D  ΔΣ=42

classify -> assign b17 -> write store record -> move to canonical dir -> return result.
One file in, one result out.
"""

import shutil
from pathlib import Path

from apps.nest.classify import classify
from apps.nest.store_bridge import gen_b17, write_file_record

TRACK_TO_DEST: dict[str, Path] = {
    "journal":         Path.home() / "personal" / "journal",
    "legal":           Path.home() / "personal" / "legal",
    "knowledge":       Path.home() / "personal" / "knowledge",
    "narrative":       Path.home() / "personal" / "writing",
    "photos_personal": Path.home() / "personal" / "photos" / "personal",
    "photos_camera":   Path.home() / "personal" / "photos" / "camera",
    "screenshots":     Path.home() / "personal" / "photos" / "screenshots",
    "handoffs":        Path.home() / "Ashokoa" / "Filed" / "reference" / "handoffs",
    "specs":           Path.home() / "Ashokoa" / "Filed" / "specs",
}

TRACK_TO_NEXT_STAGE: dict[str, str] = {
    "journal":         "compost",
    "legal":           "scrub",
    "handoffs":        "compost",
    "knowledge":       "promote",
    "narrative":       "compost",
    "specs":           "compost",
    "photos_personal": "archive",
    "photos_camera":   "archive",
    "screenshots":     "archive",
}


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


def propose(src: Path) -> dict:
    """Classify and propose a destination without moving anything."""
    track    = classify(src.name)
    dest_dir = TRACK_TO_DEST.get(track) if track else None
    proposed = str(_unique_dest(dest_dir, src.name)) if dest_dir else None
    return {
        "filename":      src.name,
        "track":         track or "unknown",
        "proposed_dest": proposed,
        "next_stage":    TRACK_TO_NEXT_STAGE.get(track or "", "archive"),
    }


def route_file(src: Path) -> dict:
    """Full intake: classify -> b17 -> store record -> move -> return result."""
    if not src.exists():
        raise FileNotFoundError(f"Source not found: {src}")

    track = classify(src.name)
    b17   = gen_b17()

    if track and track in TRACK_TO_DEST:
        dest_dir = TRACK_TO_DEST[track]
        dest_dir.mkdir(parents=True, exist_ok=True)
        final_dest = _unique_dest(dest_dir, src.name)
        shutil.move(str(src), str(final_dest))
    else:
        final_dest = src
        track      = "unknown"

    write_file_record(
        b17=b17,
        path=str(final_dest),
        filename=src.name,
        track=track,
        status="sorted" if track != "unknown" else "quarantine",
        moved_to=str(final_dest) if final_dest != src else None,
    )

    return {
        "b17":        b17,
        "filename":   src.name,
        "track":      track,
        "moved_to":   str(final_dest),
        "status":     "sorted" if track != "unknown" else "quarantine",
        "next_stage": TRACK_TO_NEXT_STAGE.get(track, "archive"),
    }
