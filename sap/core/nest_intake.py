"""
nest_intake.py — Nest intake backend for MCP tools.
b17: B2DA2  ΔΣ=42

Called by sap_mcp.py for willow_nest_scan / willow_nest_queue / willow_nest_file.
Manages the review queue at $WILLOW_HOME/nest-queue.json.

Feedback edge (nest/v1, docs/NEST_FEEDBACK_SCHEMA.md): every human gate action
(confirm / override / skip) writes an intake record carrying both the
classifier's prediction and the human outcome. Mismatches increment a
corpus/nest_corrections counter (same upsert pattern as tool_denials); at
CORRECTION_FLAG_THRESHOLD a flag opens proposing a rule delta for ratification.
The classifier never rewrites its own rules — it proposes, the human ratifies.
"""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from willow.fylgja.willow_home import willow_home

from sap.core import nest_rules

_FLEET_HOME = willow_home()

# Overrides of the same (predicted → outcome, ext) pattern before a
# rule-delta flag opens for human ratification.
CORRECTION_FLAG_THRESHOLD = 3

CORRECTIONS_COLLECTION = "corpus/nest_corrections"

NEST_DIRS = [
    Path.home() / "Desktop" / "Nest",
    _FLEET_HOME / "Nest" / "processed",
]

QUEUE_FILE = _FLEET_HOME / "nest-queue.json"

TRACK_TO_DEST = {
    # USER's files — ~/personal/
    "journal":         Path.home() / "personal" / "journal",
    "legal":           Path.home() / "personal" / "legal",
    "knowledge":       Path.home() / "personal" / "knowledge",
    "narrative":       Path.home() / "personal" / "writing",
    "photos_personal": Path.home() / "personal" / "photos" / "personal",
    "photos_camera":   Path.home() / "personal" / "photos" / "camera",
    "screenshots":     Path.home() / "personal" / "photos" / "screenshots",
    # Agent artifacts — $WILLOW_HOME/
    "handoffs":        _FLEET_HOME / "handoffs" / "filed",
    "specs":           _FLEET_HOME / "specs",
}


def _classify(filename: str) -> str | None:
    """Classify via the rules store (seed template + local overrides)."""
    return nest_rules.classify(filename)


def _track_for_dest(dest: Path) -> str:
    """Reverse-map a destination path to its track. Unknown dirs → 'custom'."""
    try:
        resolved = dest.resolve()
    except OSError:
        resolved = dest
    for track, root in TRACK_TO_DEST.items():
        try:
            root_resolved = root.resolve()
        except OSError:
            root_resolved = root
        if resolved == root_resolved or root_resolved in resolved.parents:
            return track
    return "custom"


def _prediction_for(filename: str, proposed_dest: str | None) -> dict:
    """Freeze what the classifier proposed and why, at scan time."""
    track = _classify(filename)
    return {
        "track": track or "unknown",
        "dest": proposed_dest,
        "method": "heuristic" if track else "none",
        "confidence": 0.70 if track else 0.0,
        "classifier_version": nest_rules.version(),
    }


def _load_queue() -> list[dict]:
    if not QUEUE_FILE.exists():
        return []
    return json.loads(QUEUE_FILE.read_text())


def _save_queue(queue: list[dict]) -> None:
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(json.dumps(queue, indent=2, default=str))


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


def scan_nest() -> list[dict]:
    """Scan drop zones, classify new files, stage in queue. Returns newly staged items."""
    queue = _load_queue()
    existing_paths = {item["src"] for item in queue if item["status"] == "pending"}
    newly_staged = []

    for nest_dir in NEST_DIRS:
        if not nest_dir.exists():
            continue
        for f in sorted(nest_dir.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            src = str(f)
            if src in existing_paths:
                continue
            track = _classify(f.name)
            dest_dir = TRACK_TO_DEST.get(track) if track else None
            proposed = str(_unique_dest(dest_dir, f.name)) if dest_dir else None
            item = {
                "id": len(queue) + len(newly_staged) + 1,
                "src": src,
                "filename": f.name,
                "track": track or "unknown",
                "proposed_dest": proposed,
                "prediction": _prediction_for(f.name, proposed),
                "status": "pending",
                "staged_at": datetime.now(timezone.utc).isoformat(),
            }
            newly_staged.append(item)

    if newly_staged:
        queue.extend(newly_staged)
        _save_queue(queue)

    return newly_staged


def get_queue() -> list[dict]:
    return [item for item in _load_queue() if item["status"] == "pending"]


def _item_prediction(item: dict) -> dict:
    """Prediction for an item; queue rows staged before nest/v1 lack one."""
    pred = item.get("prediction")
    if isinstance(pred, dict) and "track" in pred:
        return pred
    return {
        "track": item.get("track", "unknown"),
        "dest": item.get("proposed_dest"),
        "method": "heuristic" if item.get("track", "unknown") != "unknown" else "none",
        "confidence": 0.70 if item.get("track", "unknown") != "unknown" else 0.0,
        "classifier_version": "pre-nest-v1",
    }


def _correction_rule_key(predicted: str, outcome: str, ext: str) -> str:
    return hashlib.md5(f"{predicted}->{outcome}:{ext}".encode()).hexdigest()[:8]


def _record_correction(prediction: dict, outcome_track: str, filename: str, agent: str) -> None:
    """Count a prediction miss; open a rule-delta flag at threshold.

    Same upsert-by-rule-key pattern as tool_denials / block_telemetry: the
    counter lives in corpus/nest_corrections, the flag (once) in {agent}/flags.
    """
    from core import soil

    ext = Path(filename).suffix.lower()
    predicted = prediction.get("track", "unknown")
    rule_key = _correction_rule_key(predicted, outcome_track, ext)
    record_id = f"nest-corr-{rule_key}"
    now = datetime.now(timezone.utc).isoformat()

    existing = soil.get(CORRECTIONS_COLLECTION, record_id)
    if existing:
        existing["count"] = int(existing.get("count", 1)) + 1
        existing["last_seen"] = now
        samples = existing.get("sample_filenames", [])
        if filename not in samples:
            existing["sample_filenames"] = (samples + [filename])[-5:]
        record = existing
    else:
        record = {
            "id": record_id,
            "type": "nest_correction",
            "rule_key": rule_key,
            "predicted_track": predicted,
            "outcome_track": outcome_track,
            "ext": ext,
            "classifier_version": prediction.get("classifier_version", ""),
            "sample_filenames": [filename],
            "count": 1,
            "first_seen": now,
            "last_seen": now,
            "b17": "B2DA2",
        }
    soil.put(CORRECTIONS_COLLECTION, record_id, record)

    if int(record["count"]) >= CORRECTION_FLAG_THRESHOLD:
        flag_id = f"flag-nest-{rule_key}"
        flags_collection = f"{agent}/flags"
        if soil.get(flags_collection, flag_id) is None:
            samples = ", ".join(record["sample_filenames"][:3])
            soil.put(flags_collection, flag_id, {
                "id": flag_id,
                "type": "flag",
                "flag_state": "open",
                "title": (f"Nest classifier overridden {record['count']}×: "
                          f"{predicted} → {outcome_track} on {ext or 'no-ext'} files"),
                "source": "nest_feedback",
                "rule_key": rule_key,
                "hit_count": int(record["count"]),
                "sample_reason": f"e.g. {samples}",
                "fix_path": (f"Propose keyword/rule delta moving this pattern to "
                             f"'{outcome_track}' in the nest rules store (see "
                             f"corpus/nest_corrections {record_id}); human ratifies, "
                             f"delta applies to $WILLOW_HOME/nest_rules.json and "
                             f"bumps its version."),
                "opened_at": now,
                "b17": "B2DA2",
            })


def _write_feedback(item: dict, event: str, final_dest: Path | None) -> None:
    """Write the nest/v1 intake record for a human gate action.

    Best-effort — never blocks file ops. The record carries the frozen
    prediction and the observed outcome so promote/learning passes can
    compute error without re-reading moved files.
    """
    try:
        from core.intake import write as intake_write
        from core.agent_identity import require_agent_name
        agent = require_agent_name()

        prediction = _item_prediction(item)
        filename = item["filename"]

        if event == "skip":
            outcome = {"track": None, "dest": None, "matched": None}
            content = f"Nest skipped: {filename} (predicted {prediction['track']})"
            tier, confidence = "observed", 0.5
            track_for_tags = prediction["track"]
        else:
            outcome_track = _track_for_dest(final_dest.parent)
            matched = outcome_track == prediction["track"]
            outcome = {
                "track": outcome_track,
                "dest": str(final_dest),
                "matched": matched,
            }
            content = f"Nest {event}: {filename} → {final_dest} (track: {outcome_track})"
            tier, confidence = "verified", 1.0
            track_for_tags = outcome_track
            if not matched:
                try:
                    _record_correction(prediction, outcome_track, filename, agent)
                except Exception:
                    pass  # counter is additive telemetry — never block the record

        intake_write(
            content=content,
            source=f"nest/{event}",
            agent=agent,
            tier=tier,
            confidence=confidence,
            keywords=[track_for_tags, filename],
            tags=["nest", event, track_for_tags],
            title=f"Nest: {filename}",
            extra={
                "schema": "nest/v1",
                "event": event,
                "prediction": prediction,
                "outcome": outcome,
                "features": {
                    "filename": filename,
                    "ext": Path(filename).suffix.lower(),
                },
            },
        )
    except Exception:
        pass  # intake write is best-effort — never block file ops


def confirm_review(item_id: int, override_dest: str | None = None) -> dict:
    queue = _load_queue()
    item = next((i for i in queue if i["id"] == item_id), None)
    if not item:
        return {"error": f"item {item_id} not found"}

    src = Path(item["src"])
    if not src.exists():
        item["status"] = "error"
        item["error"] = "source file missing"
        _save_queue(queue)
        return {"error": f"source file missing: {src}"}

    dest = Path(override_dest) if override_dest else (
        Path(item["proposed_dest"]) if item["proposed_dest"] else None
    )
    if not dest:
        return {"error": "no destination — track unknown, use override_dest"}

    dest.parent.mkdir(parents=True, exist_ok=True)
    final_dest = _unique_dest(dest.parent, dest.name)
    shutil.move(str(src), str(final_dest))

    outcome_track = _track_for_dest(final_dest.parent)
    prediction = _item_prediction(item)
    event = "confirm" if outcome_track == prediction["track"] else "override"

    item["status"] = "confirmed"
    item["event"] = event
    item["outcome_track"] = outcome_track
    item["final_dest"] = str(final_dest)
    item["confirmed_at"] = datetime.now(timezone.utc).isoformat()
    _save_queue(queue)

    _write_feedback(item, event, final_dest)

    return {
        "status": "confirmed",
        "event": event,
        "item_id": item_id,
        "filename": item["filename"],
        "track": outcome_track,
        "predicted_track": prediction["track"],
        "moved_to": str(final_dest),
    }


def skip_item(item_id: int) -> dict:
    queue = _load_queue()
    item = next((i for i in queue if i["id"] == item_id), None)
    if not item:
        return {"error": f"item {item_id} not found"}
    item["status"] = "skipped"
    item["skipped_at"] = datetime.now(timezone.utc).isoformat()
    _save_queue(queue)
    _write_feedback(item, "skip", None)
    return {"status": "skipped", "item_id": item_id, "filename": item["filename"]}
