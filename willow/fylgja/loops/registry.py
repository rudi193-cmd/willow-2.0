"""Loop registry — declarative inventory per ADR-20260705-loop-registry."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable

SOIL_COLLECTION = "willow/loops"
VERIFY_CLASSES = frozenset({"recount", "exitcode", "schema", "coverage", "containment"})
ON_FAILURE = frozenset({"self_heal", "queue_decision", "open_flag"})
REVIEW_QUEUES = frozenset({"mem_ratify", "human_required"})
_TRIGGER_KINDS = frozenset({"timer", "hook", "daemon"})


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def seed_path() -> Path:
    return repo_root() / "fylgja" / "config" / "loops.json"


def schema_path() -> Path:
    return repo_root() / "fylgja" / "config" / "loops.schema.json"


def load_seed() -> dict:
    return json.loads(seed_path().read_text(encoding="utf-8"))


def load_soil_records(soil_all: Callable[[str], list[dict]] | None = None) -> dict[str, dict]:
    if soil_all is None:
        try:
            from core import soil

            rows = soil.all_records(SOIL_COLLECTION)
        except Exception:
            return {}
    else:
        rows = soil_all(SOIL_COLLECTION)
    out: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        lid = str(row.get("id") or row.get("_id") or "").strip()
        if lid:
            out[lid] = row
    return out


def load_registry(soil_all: Callable[[str], list[dict]] | None = None) -> list[dict]:
    """SOIL overlays seed JSON by loop id."""
    seed = load_seed().get("loops") or []
    by_id = {str(row["id"]): dict(row) for row in seed if isinstance(row, dict) and row.get("id")}
    by_id.update(load_soil_records(soil_all))
    return [by_id[k] for k in sorted(by_id)]


def sync_seed_to_soil(soil_put: Callable[[str, str, dict], None] | None = None) -> int:
    if soil_put is None:
        from core import soil

        soil_put = soil.put
    count = 0
    for loop in load_seed().get("loops") or []:
        if not isinstance(loop, dict) or not loop.get("id"):
            continue
        soil_put(SOIL_COLLECTION, str(loop["id"]), loop)
        count += 1
    return count


def _validate_schema(loop: dict) -> list[str]:
    path = schema_path()
    if not path.is_file():
        return []
    try:
        import jsonschema

        schema = json.loads(path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        return [f"schema: {err.message}" for err in validator.iter_errors(loop)]
    except ImportError:
        return []
    except Exception as exc:
        return [f"schema load failed: {exc}"]


def validate_loop(loop: dict) -> list[str]:
    problems: list[str] = []
    if not isinstance(loop, dict):
        return ["loop is not an object"]
    lid = str(loop.get("id") or "")
    if not lid:
        problems.append("missing id")
    heartbeat = loop.get("heartbeat")
    if not isinstance(heartbeat, dict) or not str(heartbeat.get("watchmen_key") or "").strip():
        problems.append(f"{lid or '?'}: heartbeat.watchmen_key required")
    verify = loop.get("verify") or {}
    vclass = verify.get("class")
    if vclass == "containment":
        if loop.get("on_failure") != "queue_decision":
            problems.append(f"{lid}: containment loops must set on_failure=queue_decision")
        rq = loop.get("review_queue")
        if rq not in REVIEW_QUEUES:
            problems.append(f"{lid}: containment loops require review_queue mem_ratify|human_required")
    trigger = loop.get("trigger") or {}
    kind = trigger.get("kind")
    if kind not in _TRIGGER_KINDS:
        problems.append(f"{lid}: trigger.kind must be timer|hook|daemon")
    if kind in {"timer", "daemon"} and not str(trigger.get("unit") or "").strip():
        problems.append(f"{lid}: trigger.unit required for {kind}")
    if kind == "hook" and not str(trigger.get("event") or trigger.get("name") or "").strip():
        problems.append(f"{lid}: trigger.event required for hook")
    problems.extend(_validate_schema(loop))
    return problems


def validate_registry(loops: list[dict] | None = None) -> list[str]:
    loops = loops if loops is not None else load_registry()
    problems: list[str] = []
    seen: set[str] = set()
    for loop in loops:
        lid = str(loop.get("id") or "")
        if lid in seen:
            problems.append(f"duplicate id: {lid}")
        seen.add(lid)
        problems.extend(validate_loop(loop))
    return problems


def _repo_timer_units() -> set[str]:
    units: set[str] = set()
    systemd = Path(__file__).resolve().parents[3] / "systemd"
    if not systemd.is_dir():
        return units
    for timer in systemd.glob("*.timer"):
        units.add(timer.name)
    return units


def _live_systemd_timers() -> set[str] | None:
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "list-unit-files", "*.timer", "--no-legend", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return {line.split()[0] for line in proc.stdout.splitlines() if line.strip()}


def _hook_names() -> set[str] | None:
    try:
        from willow.hooks.registry import get_active_hooks

        return {h["name"] for h in get_active_hooks()}
    except Exception:
        return None


def recount(loops: list[dict] | None = None) -> dict:
    """Compare registry records to repo systemd units and hook_registry."""
    loops = loops if loops is not None else load_registry()
    active = [loop for loop in loops if loop.get("status", "active") != "retired"]

    registry_timers = {
        str((loop.get("trigger") or {}).get("unit"))
        for loop in active
        if (loop.get("trigger") or {}).get("kind") == "timer"
    }
    registry_timers.discard("")

    external_timers = {
        str((loop.get("trigger") or {}).get("unit"))
        for loop in active
        if (loop.get("trigger") or {}).get("kind") == "timer"
        and (loop.get("trigger") or {}).get("external")
    }
    external_timers.discard("")

    registry_hooks = {
        str((loop.get("trigger") or {}).get("event") or (loop.get("trigger") or {}).get("name"))
        for loop in active
        if (loop.get("trigger") or {}).get("kind") == "hook"
    }
    registry_hooks.discard("")

    repo_timers = _repo_timer_units()
    live_timers = _live_systemd_timers()
    live_hooks = _hook_names()

    tracked_registry = registry_timers - external_timers
    if live_timers is not None:
        missing_in_reality = sorted(tracked_registry - live_timers)
        reality_source = "systemd"
    else:
        missing_in_reality = sorted(tracked_registry - repo_timers)
        reality_source = "repo_systemd_dir"

    untracked_timers = sorted(
        u for u in (repo_timers - registry_timers)
        if "bridge-cross-runtime" not in u
    )

    hook_drift: dict[str, list[str]] = {"missing_in_registry": [], "missing_in_reality": []}
    if live_hooks is not None and registry_hooks:
        hook_drift["missing_in_reality"] = sorted(registry_hooks - live_hooks)
        hook_drift["missing_in_registry"] = sorted(live_hooks - registry_hooks)

    ok = not missing_in_reality and not untracked_timers
    if live_hooks is not None and registry_hooks:
        ok = ok and not hook_drift["missing_in_reality"] and not hook_drift["missing_in_registry"]

    return {
        "ok": ok,
        "registry_timer_count": len(registry_timers),
        "reality_timer_source": reality_source,
        "external_timers": sorted(external_timers),
        "missing_in_reality": missing_in_reality,
        "untracked_timers": untracked_timers,
        "hook_drift": hook_drift,
        "live_hooks_available": live_hooks is not None,
    }
