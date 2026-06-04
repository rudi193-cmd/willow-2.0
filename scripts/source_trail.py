#!/usr/bin/env python3
"""
source-trail CLI — verify factual claims in a text file against trusted sources.

Usage:
    python3 scripts/source_trail.py verify <file>
    python3 scripts/source_trail.py verify <file> --sources pubmed,europepmc
    python3 scripts/source_trail.py verify <file> --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_verify(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8", errors="replace")
    sources = [s.strip() for s in args.sources.split(",")] if args.sources else None

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.source_trail import verify_text

    result = verify_text(text, sources=sources)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    claims = result.get("claims", [])
    total = result.get("total", 0)
    matched = result.get("matched", 0)

    print(f"\nsource-trail — {path.name}")
    print(f"{matched}/{total} claims matched\n")
    for i, c in enumerate(claims, 1):
        status = "✓" if c.get("matched") else "✗"
        tier = f"[{c['tier']}]" if c.get("tier") else ""
        conf = f"{c['confidence']:.0%}" if c.get("confidence") else ""
        print(f"  {status} [{i}] {c['claim'][:120]}")
        if c.get("matched"):
            print(f"       → {c['title'][:80]} {tier} {conf}")
            print(f"         {c['url']}")
        print()

    return 0 if matched > 0 else 2


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="source-trail",
        description="Verify factual claims against trusted sources.",
    )
    sub = parser.add_subparsers(dest="command")

    p_verify = sub.add_parser("verify", help="Verify claims in a text file")
    p_verify.add_argument("file", help="Path to the text file")
    p_verify.add_argument(
        "--sources", default="",
        help="Comma-separated source IDs (default: auto-route per claim)",
    )
    p_verify.add_argument(
        "--json", action="store_true",
        help="Output raw JSON instead of formatted report",
    )

    args = parser.parse_args()
    if args.command == "verify":
        sys.exit(cmd_verify(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
