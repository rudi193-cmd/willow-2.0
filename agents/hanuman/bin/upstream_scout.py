#!/usr/bin/env python3
"""
upstream_scout.py — Find new upstream OSS targets for Willow contributions.
b17: UPST1  ΔΣ=42

Deterministic GitHub search + heuristics. Stores candidates in SOIL for review.
Human decides before any fork/PR work.

Usage:
    upstream_scout.py run-once
    upstream_scout.py list
    upstream_scout.py show <repo_slug>   # owner-name with slashes as --
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, _ROOT)

from core import soil

_SOIL_DISCOVERY = "upstream_steward/discovery"
_SOIL_CURSOR = "upstream_steward/scout_cursor"
_CONFIG_FILE = Path.home() / ".willow" / "upstream_steward" / "config.yaml"

_SEARCH_QUERIES = [
    "mcp-server postgres stars:50..2000",
    "pgvector memory agent stars:50..2000",
    "local-first llm agent python stars:50..2000",
    "fastmcp postgres stars:30..1500",
    "agent memory mcp python stars:50..2000",
]

_CONTRIBUTORS_FILE = Path(_ROOT) / "CONTRIBUTORS.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(repo: str) -> str:
    return repo.replace("/", "--")


def _load_exclude() -> set[str]:
    excluded: set[str] = set()
    if _CONFIG_FILE.exists():
        try:
            import yaml  # type: ignore
            cfg = yaml.safe_load(_CONFIG_FILE.read_text()) or {}
            for r in cfg.get("watch_repos", []):
                excluded.add(r.lower())
        except Exception:
            pass
    if _CONTRIBUTORS_FILE.exists():
        for m in re.finditer(r"github\.com/([^/\)]+/[^/\)]+)", _CONTRIBUTORS_FILE.read_text()):
            excluded.add(m.group(1).lower())
    excluded.add("rudi193-cmd/willow-2.0")
    return excluded


def _gh_search_repos(query: str, limit: int = 15) -> list[dict]:
    try:
        result = subprocess.run(
            ["gh", "api", "-X", "GET", "search/repositories",
             "-f", f"q={query}", "-f", f"per_page={limit}",
             "-f", "sort=updated"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        return data.get("items", [])
    except Exception:
        return []


def _repo_issues(repo: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--repo", repo, "--state", "open",
             "--limit", "5", "--json", "number,title,labels,url"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return []
        return json.loads(result.stdout)
    except Exception:
        return []


def _score_repo(repo: str, meta: dict, issues: list[dict], excluded: set[str]) -> dict | None:
    name = meta.get("full_name") or repo
    if name.lower() in excluded:
        return None
    stars = meta.get("stargazers_count") or meta.get("stargazerCount") or 0
    if stars < 30 or stars > 2500:
        return None
    if meta.get("archived") or meta.get("disabled"):
        return None
    license_spdx = (meta.get("license") or {}).get("spdx_id") or ""
    if license_spdx and license_spdx not in ("MIT", "Apache-2.0", "BSD-3-Clause", "ISC"):
        return None

    desc = (meta.get("description") or "").lower()
    topics = [t.lower() for t in (meta.get("topics") or [])]
    text = desc + " " + " ".join(topics)

    fit_keywords = (
        "mcp", "postgres", "pgvector", "memory", "agent", "llm", "ollama",
        "local", "embedding", "vector", "fastmcp",
    )
    fit_hits = sum(1 for k in fit_keywords if k in text)
    if fit_hits < 1:
        return None

    doc_issue = None
    good_issue = None
    for iss in issues:
        title_l = iss.get("title", "").lower()
        labels = {lb.get("name", "").lower() for lb in iss.get("labels", [])}
        if any(l in labels for l in ("good first issue", "help wanted", "documentation")):
            good_issue = iss
        if "doc" in title_l or "document" in title_l:
            doc_issue = iss
    entry = good_issue or doc_issue

    boost = ""
    if doc_issue:
        boost = f"Docs gap: #{doc_issue['number']} — {doc_issue['title'][:80]}"
    elif good_issue:
        boost = f"Help wanted: #{good_issue['number']} — {good_issue['title'][:80]}"
    elif issues:
        boost = f"Open: #{issues[0]['number']} — {issues[0]['title'][:80]}"
    else:
        boost = "No open issues — propose small integration/doc PR from README gaps"

    confidence = min(0.94, 0.45 + fit_hits * 0.08 + (0.15 if entry else 0) + (0.05 if stars < 800 else 0))

    return {
        "repo": name,
        "stars": stars,
        "why_fit": f"{desc[:160] or 'No description'} (topics: {', '.join(topics[:4]) or 'none'})",
        "boost_angle": boost,
        "entry_issue": entry.get("url") if entry else None,
        "last_push": (meta.get("pushed_at") or meta.get("updated_at") or "")[:10],
        "confidence": round(confidence, 2),
        "discovered_at": _now(),
        "status": "candidate",
    }


def _fetch_repo_meta(repo: str) -> dict:
    try:
        result = subprocess.run(
            ["gh", "repo", "view", repo,
             "--json", "nameWithOwner,description,stargazerCount,licenseInfo,"
             "pushedAt,updatedAt,isArchived,repositoryTopics"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return {}
        data = json.loads(result.stdout)
        topics = [t.get("name", "") for t in data.get("repositoryTopics", [])]
        return {
            "full_name": data.get("nameWithOwner"),
            "description": data.get("description"),
            "stargazers_count": data.get("stargazerCount"),
            "license": {"spdx_id": (data.get("licenseInfo") or {}).get("spdxId")},
            "pushed_at": data.get("pushedAt"),
            "updated_at": data.get("updatedAt"),
            "archived": data.get("isArchived"),
            "topics": topics,
        }
    except Exception:
        return {}


def run_once(*, seed_manual: list[dict] | None = None) -> dict:
    excluded = _load_exclude()
    seen: set[str] = set()
    candidates: list[dict] = []

    if seed_manual:
        for c in seed_manual:
            repo = c.get("repo", "")
            if repo and repo.lower() not in excluded:
                c.setdefault("discovered_at", _now())
                c.setdefault("status", "candidate")
                candidates.append(c)
                seen.add(repo.lower())

    for query in _SEARCH_QUERIES:
        for item in _gh_search_repos(query):
            repo = item.get("full_name") or ""
            if not repo or repo.lower() in seen:
                continue
            seen.add(repo.lower())
            issues = _repo_issues(repo)
            scored = _score_repo(repo, item, issues, excluded)
            if scored:
                candidates.append(scored)

    candidates.sort(
        key=lambda c: (
            -bool(c.get("vetted")),
            -c.get("confidence", 0),
            -c.get("stars", 0),
        )
    )
    top = candidates[:10]

    prev = soil.get(_SOIL_CURSOR, "main") or {}
    prev_top = (prev.get("top_pick") or {}).get("repo", "")

    for c in top:
        soil.put(_SOIL_DISCOVERY, _slug(c["repo"]), c)

    top_pick = top[0] if top else {}
    cursor = {
        "last_run": _now(),
        "top_pick": top_pick,
        "candidate_count": len(top),
        "new_top": bool(top_pick and top_pick.get("repo") != prev_top),
    }
    soil.put(_SOIL_CURSOR, "main", cursor)

    print(f"upstream_scout: {len(top)} candidates stored", flush=True)
    if top_pick:
        print(f"  top_pick: {top_pick['repo']} (confidence {top_pick.get('confidence')})", flush=True)
    return cursor


def cmd_list() -> None:
    records = soil.all_records(_SOIL_DISCOVERY)
    active = [r for r in records if r.get("status") != "dismissed"]
    active.sort(key=lambda r: (-r.get("confidence", 0), -r.get("stars", 0)))
    if not active:
        print("No discovery candidates. Run: willow.sh upstream scout")
        return
    cursor = soil.get(_SOIL_CURSOR, "main") or {}
    top = (cursor.get("top_pick") or {}).get("repo", "")
    for r in active[:15]:
        mark = "★" if r.get("repo") == top else " "
        print(f"  {mark} [{r.get('confidence', 0):.2f}] {r.get('stars', 0):4d}★  {r.get('repo','')}")
        print(f"       {r.get('boost_angle','')[:70]}")


def cmd_show(slug: str) -> None:
    repo = slug.replace("--", "/")
    r = soil.get(_SOIL_DISCOVERY, slug) or soil.get(_SOIL_DISCOVERY, _slug(repo))
    if not r:
        print(f"Not found: {slug}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(r, indent=2))


def cmd_dismiss(slug: str) -> None:
    repo = slug.replace("--", "/")
    key = _slug(repo)
    r = soil.get(_SOIL_DISCOVERY, key)
    if not r:
        print(f"Not found: {slug}", file=sys.stderr)
        sys.exit(1)
    r["status"] = "dismissed"
    r["dismissed_at"] = _now()
    soil.put(_SOIL_DISCOVERY, key, r)
    print(f"  dismissed: {repo}")


# Curated first pass from agent scout (2026-05-25)
_SEED = [
    {
        "repo": "alash3al/stash",
        "stars": 701,
        "why_fit": "Postgres + pgvector agent memory with MCP server and Ollama embedders — miniature Willow stack.",
        "boost_angle": "Close #6: post-install usage guide + fix broken MCP install buttons on docs site; add Cursor mcp.json SSE snippet.",
        "entry_issue": "https://github.com/alash3al/stash/issues/6",
        "last_push": "2026-05-01",
        "confidence": 0.91,
        "vetted": True,
    },
    {
        "repo": "holon-run/holon",
        "stars": 104,
        "why_fit": "Local-first durable agent runtime (WorkItems, sleep/wake) — aligns with Willow handoffs and fleet agents.",
        "boost_angle": "Fix #1416 scheduler busy-loop when Sleep waits on background command_task.",
        "entry_issue": "https://github.com/holon-run/holon/issues/1416",
        "last_push": "2026-05-25",
        "confidence": 0.84,
        "vetted": True,
    },
    {
        "repo": "call518/MCP-PostgreSQL-Ops",
        "stars": 149,
        "why_fit": "FastMCP Postgres ops server — complements Willow's Postgres KB daily ops.",
        "boost_angle": "Add pgvector health tools: list_vector_indexes, extension_health, embedding column stats.",
        "entry_issue": None,
        "last_push": "2026-05-19",
        "confidence": 0.76,
        "vetted": True,
    },
]


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("run-once", "scout"):
        run_once(seed_manual=_SEED)
    elif args[0] == "list":
        cmd_list()
    elif args[0] == "show" and len(args) > 1:
        cmd_show(args[1])
    elif args[0] == "dismiss" and len(args) > 1:
        cmd_dismiss(args[1])
    else:
        print("Usage: upstream_scout.py [run-once|list|show <slug>|dismiss <slug>]")
        sys.exit(1)
