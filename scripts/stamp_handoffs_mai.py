#!/usr/bin/env python3
"""Add @markdownai v1.0 to handoff .md files missing it (skip archive/ and tasks/)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sap.mai.tools import _is_markdownai_content

_HEADER = "@markdownai v1.0\n\n"
_SKIP_PARTS = {"archive", "tasks"}


def stamp_file(path: Path, *, dry_run: bool = False) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if _is_markdownai_content(raw):
        return "skip"
    t = raw.lstrip()
    if t.startswith("---"):
        end = t.find("---", 3)
        if end > 3:
            insert_at = end + 3
            new = raw[:insert_at] + "\n\n" + _HEADER + raw[insert_at:].lstrip("\n")
        else:
            new = _HEADER + raw
    else:
        new = _HEADER + raw
    if not dry_run:
        path.write_text(new, encoding="utf-8")
    return "stamped"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=str(Path.home() / "github" / ".willow" / "handoffs"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).expanduser()
    counts = {"stamped": 0, "skip": 0}
    for path in sorted(root.rglob("*.md")):
        if any(p in _SKIP_PARTS for p in path.parts):
            continue
        action = stamp_file(path, dry_run=args.dry_run)
        counts[action] = counts.get(action, 0) + 1
        if action == "stamped":
            print(("would stamp" if args.dry_run else "stamped"), path.relative_to(root))
    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
