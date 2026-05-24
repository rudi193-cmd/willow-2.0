#!/usr/bin/env python3
"""
Semantic Jukebox — CLI
======================
Usage:
  python3 tools/jukebox.py "feeling disconnected"
  python3 tools/jukebox.py "momentum and frustration" --speak
  python3 tools/jukebox.py "late nights and bad decisions" -n 12

Options:
  -n N       Number of KB atoms to pull (default: 8)
  --speak    Send script to Kokoro TTS and play it
  --json     Raw JSON output instead of formatted print
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

from core.jukebox import segment


_SEPARATOR = "─" * 60


def _play(path: str) -> None:
    for player in ("aplay", "paplay", "ffplay"):
        try:
            subprocess.run([player, path], capture_output=True, timeout=120)
            return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    print(f"[jukebox] audio saved to {path} — no player found to auto-play")


def main() -> None:
    parser = argparse.ArgumentParser(description="Semantic Jukebox — guy noir reads your KB")
    parser.add_argument("mood", nargs="+", help="mood or situation to search for")
    parser.add_argument("-n", type=int, default=8, help="atoms to retrieve (default 8)")
    parser.add_argument("--speak", action="store_true", help="send to Kokoro TTS")
    parser.add_argument("--json", action="store_true", dest="json_out", help="raw JSON output")
    args = parser.parse_args()

    mood = " ".join(args.mood)

    print(f"\n{_SEPARATOR}")
    print(f"  JUKEBOX — searching for: {mood!r}")
    print(f"{_SEPARATOR}")
    print("  ...\n")

    result = segment(mood, n=args.n, speak=args.speak)

    if args.json_out:
        import json
        print(json.dumps(result, indent=2, default=str))
        return

    # Pretty print
    script = result["script"]
    wrapped = textwrap.fill(script, width=66, initial_indent="  ", subsequent_indent="  ")

    print(f"{_SEPARATOR}")
    print()
    print(wrapped)
    print()
    print(f"{_SEPARATOR}")

    atoms = result["atoms"]
    if atoms:
        print(f"\n  [ {len(atoms)} atoms pulled from case file ]\n")
        for a in atoms[:5]:
            title = a.get("title", "(untitled)")[:55]
            tier  = a.get("tier") or "?"
            print(f"    · [{tier}] {title}")
        if len(atoms) > 5:
            print(f"    · ... and {len(atoms)-5} more")

    if result.get("audio_path"):
        print(f"\n  [ audio → {result['audio_path']} ]\n")
        _play(result["audio_path"])
    elif args.speak:
        print("\n  [ Kokoro not running — text only. Start it with: ]")
        print("  pip install kokoro soundfile && python -m kokoro.server\n")

    print()


if __name__ == "__main__":
    main()
