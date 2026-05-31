#!/usr/bin/env python3
"""Phase 4: import one external SKILL.md → draft Fylgja skill + execution class.

Semi-automated fork — human reviews before blessing. Does not copy marketplace trees;
emits a single adapted skill under willow/fylgja/skills/drafts/ by default.

Usage:
  python3 scripts/skill_adopt.py path/to/SKILL.md
  python3 scripts/skill_adopt.py path/to/SKILL.md --write
  python3 scripts/skill_adopt.py path/to/SKILL.md --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.skill_catalog_scan import classify_execution, classify_risk, scan_file

REPO = Path(__file__).resolve().parent.parent
DRAFTS = REPO / "willow" / "fylgja" / "skills" / "drafts"
WILLOW_LANE = {
    "A": "Willow MCP (kb_*, fleet_*, handoff_*, soil_*)",
    "B": "Kart: agent_task_submit → kart_task_run",
    "C": "Background loop + sentinel (see fylgja/skills/context-sentinel.md)",
    "D": "mai_write_file / templates (hooks, rules, skills)",
    "E": "Split into B + C before blessing — avoid foreground saga",
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "adopted-skill"


def draft_body(record: dict, source_path: Path, raw_body: str) -> str:
    cls = record["execution_class"]
    lane = WILLOW_LANE.get(cls, WILLOW_LANE["E"])
    trimmed = raw_body.strip()
    if len(trimmed) > 6000:
        trimmed = trimmed[:6000] + "\n\n… [truncated — edit draft before bless]\n"
    return f"""---
name: {_slug(record['name'])}
description: "{record.get('description', '')[:200].replace(chr(34), "'")}"
adopted_from: {record['id']}
execution_class: {cls}
risk: {record.get('risk', 'medium')}
status: draft
---

# {record['name']} (adopted draft)

**Source:** `{source_path}`  
**Catalog id:** `{record['id']}`  
**Execution class:** {cls} — {lane}  
**Risk:** {record.get('risk')} {record.get('risk_signals') or []}

> Review and rewrite blocking Bash / long polls to MCP or Kart before moving out of `drafts/`.

## Willow execution lane

{lane}

## Original instructions (adapt, do not run verbatim)

{trimmed}
"""


def adopt(source: Path, *, write: bool, dry_run: bool) -> dict:
    source = source.resolve()
    if not source.is_file():
        raise SystemExit(f"not a file: {source}")

    record = scan_file(source, scan_root=source.parent)
    raw = source.read_text(encoding="utf-8", errors="replace")
    _, body = __import__("sap.mai.tools", fromlist=["_strip_yaml_frontmatter"])._strip_yaml_frontmatter(raw)

    # Re-classify with explicit external default
    record["execution_class"] = classify_execution(raw, default="E")
    record["risk"], record["risk_signals"] = classify_risk(raw)
    record["status"] = "draft"
    record["adopted_at"] = datetime.now(timezone.utc).isoformat()

    out_name = _slug(record["name"]) + ".md"
    out_path = DRAFTS / out_name
    content = draft_body(record, source, body)

    result = {
        "record": record,
        "draft_path": str(out_path.relative_to(REPO)),
        "write": write and not dry_run,
    }
    if dry_run:
        result["preview_lines"] = content.splitlines()[:40]
        return result
    if write:
        DRAFTS.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
    else:
        print(content)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, help="Path to external SKILL.md")
    ap.add_argument("--write", action="store_true", help=f"Write draft under {DRAFTS.relative_to(REPO)}/")
    ap.add_argument("--dry-run", action="store_true", help="JSON summary only")
    ap.add_argument("--json", action="store_true", help="Emit result as JSON")
    args = ap.parse_args()
    result = adopt(args.source, write=args.write, dry_run=args.dry_run)
    if args.json or args.dry_run:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.write:
        print(json.dumps({"written": result["draft_path"], "execution_class": result["record"]["execution_class"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
