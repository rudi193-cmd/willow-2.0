#!/usr/bin/env python3
"""Scan SKILL.md trees and emit skill-catalog JSONL with execution class (A–E) and risk heuristics."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sap.mai.tools import _strip_yaml_frontmatter

# Curated overrides for known skills (id → extra fields). Scanner still fills path/description.
CURATED: dict[str, dict[str, Any]] = {
    "cursor/babysit": {
        "execution_class": "C",
        "risk": "medium",
        "willow_twin": "willow/fylgja/skills/babysit.md",
        "status": "adopted",
    },
    "cursor/loop": {
        "execution_class": "C",
        "risk": "low",
        "willow_twin": "willow/fylgja/skills/context-sentinel.md",
        "status": "adopted",
    },
    "cursor/shell": {
        "execution_class": "B",
        "risk": "medium",
        "willow_twin": "willow/fylgja/skills/kart.md",
        "status": "adopted",
    },
    "cursor/split-to-prs": {
        "execution_class": "E",
        "risk": "medium",
        "willow_twin": "willow/fylgja/skills/worktree.md",
        "status": "reference",
    },
    "cursor/create-hook": {
        "execution_class": "D",
        "risk": "low",
        "willow_twin": "willow/fylgja/events/",
        "status": "reference",
    },
    "cursor/create-rule": {
        "execution_class": "D",
        "risk": "low",
        "willow_twin": "willow/fylgja/config/",
        "status": "reference",
    },
    "cursor/create-skill": {
        "execution_class": "D",
        "risk": "low",
        "willow_twin": "willow/fylgja/skills/",
        "status": "reference",
    },
    "fylgja/babysit": {
        "execution_class": "C",
        "risk": "low",
        "willow_twin": "willow/fylgja/skills/babysit.md",
        "status": "blessed",
    },
    "fylgja/kart": {
        "execution_class": "B",
        "risk": "low",
        "willow_twin": "willow/fylgja/skills/kart.md",
        "status": "blessed",
    },
    "fylgja/handoff": {
        "execution_class": "A",
        "risk": "low",
        "willow_twin": "willow/fylgja/skills/handoff.md",
        "status": "blessed",
    },
}

# High-value seed catalog (~50) — phase 1 of SKILL_SURFACE_STRATEGY.md
SEED_CATALOG_IDS: list[str] = [
    # Cursor skills-cursor (14)
    "cursor/babysit",
    "cursor/loop",
    "cursor/shell",
    "cursor/split-to-prs",
    "cursor/sdk",
    "cursor/create-hook",
    "cursor/create-rule",
    "cursor/create-skill",
    "cursor/create-subagent",
    "cursor/migrate-to-skills",
    "cursor/canvas",
    "cursor/statusline",
    "cursor/update-cli-config",
    "cursor/update-cursor-settings",
    # Willow Fylgja blessed (24)
    "fylgja/babysit",
    "fylgja/kart",
    "fylgja/handoff",
    "fylgja/boot",
    "fylgja/tdd",
    "fylgja/review",
    "fylgja/willow-review",
    "fylgja/willow-deploy",
    "fylgja/debugging",
    "fylgja/investigate",
    "fylgja/worktree",
    "fylgja/worktree-enforce",
    "fylgja/grove-gate",
    "fylgja/grove-quorum",
    "fylgja/grove-persistent-monitor",
    "fylgja/fleet-dashboard",
    "fylgja/context-sentinel",
    "fylgja/health",
    "fylgja/coordinator",
    "fylgja/learn",
    "fylgja/iterative-retrieval",
    "fylgja/external-guard",
    "fylgja/power",
    "fylgja/complexity-guard",
    # awesome-claude-skills (12)
    "awesome-claude/webapp-testing",
    "awesome-claude/skill-creator",
    "awesome-claude/mcp-builder",
    "awesome-claude/changelog-generator",
    "awesome-claude/connect",
    "awesome-claude/theme-factory",
    "awesome-claude/slack-gif-creator",
    "awesome-claude/video-downloader",
    "awesome-claude/file-organizer",
    "awesome-claude/content-research-writer",
    "awesome-claude/meeting-insights-analyzer",
    "awesome-claude/developer-growth-analysis",
]

# Extra seed metadata (willow_twin / status / class overrides)
SEED_ENRICH: dict[str, dict[str, Any]] = {
    **CURATED,
    "cursor/sdk": {"execution_class": "E", "risk": "low", "willow_twin": "", "status": "reference"},
    "cursor/create-subagent": {
        "execution_class": "E",
        "risk": "medium",
        "willow_twin": "",
        "status": "reference",
    },
    "cursor/migrate-to-skills": {
        "execution_class": "E",
        "risk": "low",
        "willow_twin": "",
        "status": "reference",
    },
    "cursor/canvas": {"execution_class": "D", "risk": "low", "willow_twin": "", "status": "reference"},
    "cursor/statusline": {
        "execution_class": "D",
        "risk": "low",
        "willow_twin": "scripts/cli_statusline.sh",
        "status": "reference",
    },
    "cursor/update-cli-config": {
        "execution_class": "D",
        "risk": "low",
        "willow_twin": "",
        "status": "reference",
    },
    "cursor/update-cursor-settings": {
        "execution_class": "D",
        "risk": "low",
        "willow_twin": "",
        "status": "reference",
    },
    "fylgja/boot": {"execution_class": "A", "status": "blessed", "willow_twin": "willow/fylgja/skills/boot.md"},
    "fylgja/tdd": {"execution_class": "B", "status": "blessed", "willow_twin": "willow/fylgja/skills/tdd.md"},
    "fylgja/review": {"execution_class": "B", "status": "blessed", "willow_twin": "willow/fylgja/skills/review.md"},
    "fylgja/willow-review": {
        "execution_class": "B",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/willow-review.md",
    },
    "fylgja/willow-deploy": {
        "execution_class": "B",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/willow-deploy.md",
    },
    "fylgja/debugging": {
        "execution_class": "B",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/debugging.md",
    },
    "fylgja/investigate": {
        "execution_class": "A",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/investigate.md",
    },
    "fylgja/worktree": {
        "execution_class": "B",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/worktree.md",
    },
    "fylgja/worktree-enforce": {
        "execution_class": "B",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/worktree-enforce.md",
    },
    "fylgja/grove-gate": {
        "execution_class": "B",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/grove-gate.md",
    },
    "fylgja/grove-quorum": {
        "execution_class": "A",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/grove-quorum.md",
    },
    "fylgja/grove-persistent-monitor": {
        "execution_class": "C",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/grove-persistent-monitor.md",
    },
    "fylgja/fleet-dashboard": {
        "execution_class": "A",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/fleet-dashboard.md",
    },
    "fylgja/context-sentinel": {
        "execution_class": "C",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/context-sentinel.md",
    },
    "fylgja/health": {
        "execution_class": "A",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/health.md",
    },
    "fylgja/coordinator": {
        "execution_class": "A",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/coordinator.md",
    },
    "fylgja/learn": {"execution_class": "A", "status": "blessed", "willow_twin": "willow/fylgja/skills/learn.md"},
    "fylgja/iterative-retrieval": {
        "execution_class": "A",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/iterative-retrieval.md",
    },
    "fylgja/external-guard": {
        "execution_class": "A",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/external-guard.md",
    },
    "fylgja/power": {
        "execution_class": "A",
        "status": "blessed",
        "willow_twin": "willow/fylgja/powers/registry.json",
    },
    "fylgja/complexity-guard": {
        "execution_class": "A",
        "status": "blessed",
        "willow_twin": "willow/fylgja/skills/complexity-guard.md",
    },
    "awesome-claude/webapp-testing": {
        "execution_class": "B",
        "risk": "medium",
        "willow_twin": "willow/fylgja/skills/tdd.md",
        "status": "catalog",
    },
    "awesome-claude/skill-creator": {
        "execution_class": "D",
        "risk": "low",
        "willow_twin": "willow/fylgja/skills/",
        "status": "catalog",
    },
    "awesome-claude/mcp-builder": {
        "execution_class": "D",
        "risk": "medium",
        "willow_twin": "sap/mcp_registry.json",
        "status": "catalog",
    },
    "awesome-claude/changelog-generator": {
        "execution_class": "D",
        "risk": "low",
        "willow_twin": "",
        "status": "catalog",
    },
    "awesome-claude/connect": {
        "execution_class": "B",
        "risk": "medium",
        "willow_twin": "sap/openclaw_mcp.py",
        "status": "catalog",
    },
    "awesome-claude/theme-factory": {
        "execution_class": "D",
        "risk": "low",
        "willow_twin": "",
        "status": "catalog",
    },
    "awesome-claude/slack-gif-creator": {
        "execution_class": "B",
        "risk": "low",
        "willow_twin": "",
        "status": "catalog",
    },
    "awesome-claude/video-downloader": {
        "execution_class": "B",
        "risk": "medium",
        "willow_twin": "willow/fylgja/skills/kart.md",
        "status": "catalog",
    },
    "awesome-claude/file-organizer": {
        "execution_class": "A",
        "risk": "low",
        "willow_twin": "",
        "status": "catalog",
    },
    "awesome-claude/content-research-writer": {
        "execution_class": "A",
        "risk": "low",
        "willow_twin": "",
        "status": "catalog",
    },
    "awesome-claude/meeting-insights-analyzer": {
        "execution_class": "A",
        "risk": "low",
        "willow_twin": "",
        "status": "catalog",
    },
    "awesome-claude/developer-growth-analysis": {
        "execution_class": "A",
        "risk": "low",
        "willow_twin": "",
        "status": "catalog",
    },
}

# Regex buckets — order matters for classification (first strong match wins).
_CLASS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "E",
        re.compile(
            r"gh\s+pr\s+checks\s+--watch|"
            r"\buntil\s+(?:ready|mergeable|green)\b|"
            r"re-watch\s+ci\s+until|"
            r"fix\s+ci\s+in\s+a\s+loop|"
            r"foreground\s+saga|"
            r"stay\s+in\s+(?:the\s+)?(?:thread|session)|"
            r"babysit\s+until\s+merge",
            re.I,
        ),
    ),
    (
        "C",
        re.compile(
            r"notify_on_output|AGENT_LOOP_TICK|"
            r"background\s+(?:shell|watcher|loop)|"
            r"/loop\b|"
            r"while\s+true|"
            r"\bsentinel\b|"
            r"grove-persistent-monitor|"
            r"context-sentinel",
            re.I,
        ),
    ),
    (
        "D",
        re.compile(
            r"create[- ](?:hook|rule|skill)|"
            r"mai_write_file|"
            r"template-skill|"
            r"skill-creator|"
            r"theme-factory|"
            r"authoring",
            re.I,
        ),
    ),
    (
        "A",
        re.compile(
            r"\b(?:kb_|soil_|fleet_|handoff_)\w*|"
            r"mai_read_file|mai_write_file|"
            r"willow\s+mcp|"
            r"iterative-retrieval|"
            r"fleet-dashboard|"
            r"persistent-memory",
            re.I,
        ),
    ),
    (
        "B",
        re.compile(
            r"agent_task_submit|kart_task_run|"
            r"\b(?:git|gh|pytest|npm|cargo|make)\b|"
            r"script_body|"
            r"webapp-testing|"
            r"video-downloader",
            re.I,
        ),
    ),
]

_RISK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("curl_pipe_bash", re.compile(r"curl\s+[^\n|]*\|\s*(?:ba)?sh", re.I)),
    ("while_true", re.compile(r"while\s+true", re.I)),
    ("gh_watch", re.compile(r"gh\s+pr\s+checks\s+--watch", re.I)),
    ("requires_bins", re.compile(r"requires\.bins|requires:\s*\n\s*bins:", re.I)),
    ("env_secrets", re.compile(r"(?:API_KEY|SECRET|TOKEN)\s*=", re.I)),
    ("eval_exec", re.compile(r"\b(?:eval|exec)\s*\(", re.I)),
]

_SKILL_FILENAMES = frozenset({"SKILL.md", "skill.md"})
_FYLGJA_FLAT = re.compile(r"^[a-z0-9][a-z0-9-]*\.md$", re.I)


def _parse_frontmatter_fields(front: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not front:
        return out
    inner = front.strip()
    if inner.startswith("---"):
        inner = inner[3:]
    if inner.endswith("---"):
        inner = inner[:-3]
    lines = inner.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1).lower(), m.group(2).strip()
        if val in (">-", ">", "|", "|-") or (not val and i + 1 < len(lines)):
            # Folded / literal block scalar
            i += 1
            parts: list[str] = []
            while i < len(lines):
                nxt = lines[i]
                if re.match(r"^[A-Za-z0-9_-]+:\s*", nxt) and not nxt.startswith(" "):
                    break
                if nxt.strip():
                    parts.append(nxt.strip())
                i += 1
            out[key] = " ".join(parts)
            continue
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        out[key] = val
        i += 1
    return out


def _infer_source(root: Path, skill_path: Path) -> str:
    parts = {p.lower() for p in skill_path.parts}
    if "skills-cursor" in parts or ".cursor" in parts:
        return "cursor"
    if "fylgja" in parts and "willow" in parts:
        return "fylgja"
    if "awesome-claude-skills" in parts:
        return "awesome-claude"
    if "openclaw" in parts or "clawhub" in parts:
        return "openclaw"
    name = root.name.lower()
    if name in ("skills-cursor", "skills"):
        return "cursor"
    if name == "awesome-claude-skills":
        return "awesome-claude"
    return "homebrew"


def _skill_id(source: str, skill_path: Path, name: str) -> str:
    if skill_path.name.upper() == "SKILL.MD":
        slug = skill_path.parent.name
    else:
        slug = skill_path.stem
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-") or "unknown"
    safe_name = re.sub(r"[^a-z0-9]+", "-", (name or slug).lower()).strip("-") or slug
    if safe_name != slug and slug != "unknown":
        return f"{source}/{slug}"
    return f"{source}/{safe_name}"


def classify_execution(text: str, *, default: str = "E") -> str:
    for cls, pat in _CLASS_PATTERNS:
        if pat.search(text):
            return cls
    return default


def classify_risk(text: str) -> tuple[str, list[str]]:
    signals = [label for label, pat in _RISK_PATTERNS if pat.search(text)]
    if any(s in ("curl_pipe_bash", "eval_exec") for s in signals):
        return "high", signals
    if any(s in ("gh_watch", "while_true", "env_secrets") for s in signals):
        return "medium", signals
    if signals:
        return "low", signals
    return "low", signals


def scan_file(skill_path: Path, *, scan_root: Path | None = None) -> dict[str, Any]:
    raw = skill_path.read_text(encoding="utf-8", errors="replace")
    front, body = _strip_yaml_frontmatter(raw)
    fields = _parse_frontmatter_fields(front)
    name = fields.get("name") or skill_path.parent.name
    description = fields.get("description", "")[:500]
    source = _infer_source(scan_root or skill_path.parent, skill_path)
    skill_id = _skill_id(source, skill_path, name)
    text = raw
    execution_class = classify_execution(text, default="E" if source != "fylgja" else "B")
    risk, risk_signals = classify_risk(text)
    rel = None
    try:
        rel = str(skill_path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        rel = str(skill_path.resolve())

    record: dict[str, Any] = {
        "id": skill_id,
        "name": name,
        "source": source,
        "path": rel,
        "description": description,
        "execution_class": execution_class,
        "risk": risk,
        "risk_signals": risk_signals,
        "willow_twin": "",
        "status": "catalog" if source != "fylgja" else "blessed",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
    overlay = SEED_ENRICH.get(skill_id) or CURATED.get(skill_id)
    if overlay:
        record.update(overlay)
    return record


def iter_skill_paths(root: Path, *, include_fylgja_flat: bool = False) -> list[Path]:
    root = root.resolve()
    if not root.is_dir():
        return []
    found: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.name in _SKILL_FILENAMES:
            found.append(p)
            continue
        if include_fylgja_flat and "fylgja/skills" in str(p).replace("\\", "/"):
            if _FYLGJA_FLAT.match(p.name) and p.name.lower() != "skill.md":
                found.append(p)
    return found


def scan_roots(
    roots: list[Path],
    *,
    include_fylgja_flat: bool = False,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for root in roots:
        for path in iter_skill_paths(root, include_fylgja_flat=include_fylgja_flat):
            rec = scan_file(path, scan_root=root)
            # Prefer shallower / blessed paths on duplicate ids
            prev = by_id.get(rec["id"])
            if prev is None or rec["source"] == "fylgja":
                by_id[rec["id"]] = rec
    return sorted(by_id.values(), key=lambda r: (r["source"], r["id"]))


def write_jsonl(records: list[dict[str, Any]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_catalog_ids(catalog: Path) -> list[str]:
    ids: list[str] = []
    if not catalog.is_file():
        return ids
    for line in catalog.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        ids.append(json.loads(line)["id"])
    return ids


def filter_to_ids(records: list[dict[str, Any]], ids: list[str]) -> list[dict[str, Any]]:
    by_id = {r["id"]: r for r in records}
    out: list[dict[str, Any]] = []
    for i in ids:
        if i in by_id:
            out.append(by_id[i])
    return out


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    default_out = repo / "willow" / "skill-catalog.jsonl"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "roots",
        nargs="*",
        type=Path,
        help="Directories to scan (default: cursor skills-cursor, fylgja/skills, awesome-claude-skills)",
    )
    parser.add_argument("-o", "--output", type=Path, default=default_out)
    parser.add_argument(
        "--include-fylgja-flat",
        action="store_true",
        default=True,
        help="Include willow/fylgja/skills/*.md (default: on)",
    )
    parser.add_argument(
        "--no-fylgja-flat",
        action="store_true",
        help="Only SKILL.md under roots, not flat fylgja/*.md",
    )
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Write only ids already in output catalog (refresh in place)",
    )
    parser.add_argument(
        "--write-seed",
        action="store_true",
        help=f"Write phase-1 seed catalog ({len(SEED_CATALOG_IDS)} ids) to --output",
    )
    args = parser.parse_args()

    include_flat = args.include_fylgja_flat and not args.no_fylgja_flat
    home = Path.home()
    default_roots = [
        home / ".cursor" / "skills-cursor",
        repo / "willow" / "fylgja" / "skills",
        repo / "awesome-claude-skills",
    ]
    roots = args.roots if args.roots else [r for r in default_roots if r.is_dir()]
    if not roots:
        print("No scan roots found.", file=sys.stderr)
        return 1

    records = scan_roots(roots, include_fylgja_flat=include_flat)
    if args.write_seed:
        want = SEED_CATALOG_IDS
    elif args.seed_only and args.output.is_file():
        want = load_catalog_ids(args.output)
    else:
        want = []
    if want:
        records = filter_to_ids(records, want)
        missing = [i for i in want if i not in {r["id"] for r in records}]
        if missing:
            print(f"Warning: {len(missing)} seed ids not found: {', '.join(missing)}", file=sys.stderr)
    write_jsonl(records, args.output)
    print(f"Wrote {len(records)} records → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
