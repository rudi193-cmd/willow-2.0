"""
nest.py — Willow Nest: intake consent layer + pipeline runner.
b17: 1284BC7D  ΔΣ=42

Usage:
  python3 -m apps.nest              # scan drop zones, show consent, run on confirm
  python3 -m apps.nest --dry-run    # show plan, no moves
  python3 -m apps.nest --drain      # run pipeline on all sorted records
  python3 -m apps.nest --watch      # start drop zone daemon (watcher mode)

Drop zones:
  ~/Desktop/Nest/
  ~/Ashokoa/Nest/processed/
"""

import argparse
import sys
from pathlib import Path

from apps.nest.classify import classify
from apps.nest.router import propose, route_file, TRACK_TO_NEXT_STAGE
from apps.nest.store_bridge import get_record, update_status

PIPELINE_STAGES = {
    "compost": ("apps.nest.pipeline.compost", "run"),
    "scrub":   ("apps.nest.pipeline.scrub",   "run"),
    "promote": ("apps.nest.pipeline.promote",  "run"),
    "archive": ("apps.nest.pipeline.archive",  "run"),
}

TRACK_PIPELINE = {
    "journal":         ["compost", "promote"],
    "legal":           ["scrub"],
    "knowledge":       ["promote"],
    "narrative":       ["compost", "promote"],
    "photos_personal": [],
    "photos_camera":   [],
    "screenshots":     [],
    "handoffs":        ["compost", "promote"],
    "specs":           ["compost", "promote"],
    "unknown":         [],
}

NEST_DIRS = [
    Path.home() / "Desktop" / "Nest",
    Path.home() / "Ashokoa" / "Nest" / "processed",
]


def _run_stage(stage_name: str, b17: str) -> dict:
    module_path, fn_name = PIPELINE_STAGES[stage_name]
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, fn_name)(b17)


def run_pipeline(b17: str) -> list[dict]:
    record = get_record(b17)
    if not record:
        print(f"  ERROR: no record for {b17}")
        return []
    track  = record.get("track", "unknown")
    stages = TRACK_PIPELINE.get(track, [])
    results = []
    for stage in stages:
        print(f"  [{stage}] {b17} ...", end=" ", flush=True)
        result = _run_stage(stage, b17)
        print(result.get("status", result.get("error", "?")))
        results.append(result)
        if "error" in result:
            print(f"    !! {result['error']}")
            break
    return results


def scan_drop_zones() -> list[Path]:
    files = []
    for d in NEST_DIRS:
        if not d.exists():
            continue
        for f in sorted(d.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                files.append(f)
    return files


def show_consent(files: list[Path]) -> None:
    print(f"\n{'─'*60}")
    print(f"  NEST — {len(files)} file(s) detected")
    print(f"{'─'*60}")
    for f in files:
        p      = propose(f)
        track  = p["track"]
        dest   = p["proposed_dest"] or "QUARANTINE"
        stages = " → ".join(TRACK_PIPELINE.get(track, ["?"]))
        print(f"  {f.name}")
        print(f"    track:  {track}")
        print(f"    dest:   {dest}")
        print(f"    stages: {stages or '(none)'}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Willow Nest file intake")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--drain",   action="store_true")
    parser.add_argument("--watch",   action="store_true", help="Start drop zone daemon")
    parser.add_argument("--run-pipeline", metavar="B17")
    args = parser.parse_args()

    if args.run_pipeline:
        run_pipeline(args.run_pipeline.upper())
        return

    if args.watch:
        import time
        from apps.nest.watcher import NestWatcher

        def _handle(path: Path) -> None:
            print(f"[nest] {path.name}", end=" ", flush=True)
            try:
                result = route_file(path)
                print(f"[{result['track']}] {result['b17']}")
                run_pipeline(result["b17"])
            except Exception as exc:
                print(f"ERROR: {exc}")

        w = NestWatcher(on_file=_handle)
        w.start()
        print("Nest watcher running. Ctrl-C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            w.stop()
        return

    if args.drain:
        print("\nDrain mode requires Willow MCP connection.")
        print("  Use: WILLOW_AGENT_NAME=willow-nest python3 -m apps.nest --drain")
        return

    files = scan_drop_zones()
    if not files:
        print("\nNest is empty. Drop files into:")
        for d in NEST_DIRS:
            print(f"  {d}")
        return

    show_consent(files)

    if args.dry_run:
        print("  [dry-run] No files moved.\n")
        return

    answer = input("Proceed? [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        return

    print()
    results, quarantined = [], []
    for f in files:
        print(f"  → {f.name}", end=" ", flush=True)
        result = route_file(f)
        b17    = result["b17"]
        track  = result["track"]
        print(f"[{track}] {b17}")
        if track == "unknown":
            quarantined.append(f.name)
            continue
        run_pipeline(b17)
        results.append((b17, result))

    print(f"\n{'─'*60}")
    print(f"  Done. {len(results)} filed, {len(quarantined)} quarantined.")
    if quarantined:
        print("  Quarantined:")
        for name in quarantined:
            print(f"    {name}")
    print()


if __name__ == "__main__":
    main()
