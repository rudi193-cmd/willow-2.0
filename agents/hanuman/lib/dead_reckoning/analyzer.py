"""
dead_reckoning/analyzer.py — Weekly heading estimate.
b17: DRCK2  ΔΣ=42

Reads the last 7 days of signal (git, Think Maps, KB, Grove,
ledger observations, corrections, handoffs) and synthesises a
one-paragraph heading estimate via local LLM.
Writes a single KB atom: tier=frontier, category=dead_reckoning.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import soil

_WEEK_DAYS = 7
_THINK_MAPS_COLLECTION = "willow-dashboard/think_maps"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _since() -> str:
    return (_now() - timedelta(days=_WEEK_DAYS)).strftime("%Y-%m-%d")


def _mcp(tool: str, args: dict, timeout: int = 25) -> Any:
    try:
        from willow.fylgja._mcp import call
        return call(tool, args, timeout=timeout)
    except Exception as exc:
        return {"error": str(exc)}


# ── Signal collectors ──────────────────────────────────────────────────────────

def _collect_git(repo_root: str = _ROOT) -> dict:
    since = _since()
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--oneline", "--no-merges"],
            cwd=repo_root, capture_output=True, text=True, check=False,
        )
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        # Extract message words (skip hashes)
        messages = [" ".join(l.split()[1:]) for l in lines]
        return {"commit_count": len(messages), "messages": messages[:20]}
    except Exception as exc:
        return {"commit_count": 0, "messages": [], "error": str(exc)}


def _collect_think_maps() -> dict:
    since_dt = _now() - timedelta(days=_WEEK_DAYS)
    since_iso = since_dt.isoformat()
    records = soil.all_records(_THINK_MAPS_COLLECTION)
    confirmed = [
        r for r in records
        if r.get("status") == "confirmed"
        and (r.get("confirmed_at") or r.get("updated_at") or "") >= since_iso
    ]
    drafts = [r for r in records if r.get("status") == "draft"]
    decisions = []
    for r in confirmed:
        rec_node = next(
            (n for n in r.get("nodes", []) if n.get("kind") == "approach" and n.get("recommended")),
            None,
        )
        decisions.append({
            "problem": r.get("center", {}).get("text", "")[:80],
            "decision": rec_node["text"][:60] if rec_node else "",
        })
    open_problems = [r.get("center", {}).get("text", "")[:70] for r in drafts]
    return {
        "confirmed_count": len(confirmed),
        "decisions": decisions,
        "draft_count": len(drafts),
        "open_problems": open_problems[:5],
    }


def _collect_ledger() -> dict:
    """Read FRANK ledger for last 7 days — observations, blocks, check-ins, posts."""
    since_iso = (_now() - timedelta(days=_WEEK_DAYS)).isoformat()
    result = _mcp("ledger_read", {"app_id": "hanuman", "limit": 100})
    if isinstance(result, dict) and result.get("error"):
        return {"error": result["error"], "observations": [], "blocks": 0,
                "checkins": [], "posts": 0, "projects_touched": []}

    entries = result.get("entries", []) if isinstance(result, dict) else []
    recent = [e for e in entries if (e.get("created_at") or "") >= since_iso]

    observations, blocks, checkins, posts, projects = [], 0, [], 0, set()

    for e in recent:
        etype = e.get("event_type", "")
        project = e.get("project", "")
        if project:
            projects.add(project)
        content = e.get("content", {})

        if etype == "observation":
            text = content if isinstance(content, str) else content.get("text", str(content))
            observations.append(str(text)[:100])
        elif etype == "block":
            blocks += 1
        elif etype == "check_in":
            summary = content.get("summary", "") if isinstance(content, dict) else str(content)
            next_bite = content.get("next_bite", "") if isinstance(content, dict) else ""
            checkins.append({"summary": summary[:120], "next": next_bite[:80]})
        elif etype in ("upstream.posted", "posted"):
            posts += 1

    return {
        "observation_count": len(observations),
        "observations": observations[:10],
        "block_count": blocks,
        "checkin_count": len(checkins),
        "checkins": checkins[:3],
        "post_count": posts,
        "projects_touched": sorted(projects),
    }


def _collect_handoffs() -> dict:
    """Fetch latest handoff summary and open threads."""
    result = _mcp("handoff_latest", {"app_id": "hanuman"})
    if isinstance(result, dict) and result.get("error"):
        return {"summary": "", "open_threads": [], "date": ""}
    if not isinstance(result, dict):
        return {"summary": "", "open_threads": [], "date": ""}
    summary = result.get("summary", "")[:400]
    threads = result.get("open_threads", [])
    thread_texts = []
    for t in threads[:5]:
        if isinstance(t, str):
            thread_texts.append(t[:80])
        elif isinstance(t, dict):
            thread_texts.append(str(t.get("text", t.get("title", "")))[:80])
    return {
        "summary": summary,
        "open_threads": thread_texts,
        "date": result.get("date", ""),
    }


def _collect_kb_atoms() -> dict:
    since = _since()
    result = _mcp("kb_search", {
        "app_id": "hanuman",
        "query": "session week agent willow",
        "limit": 10,
        "semantic": True,
    })
    atoms = []
    if isinstance(result, dict):
        for item in result.get("knowledge", [])[:8]:
            created = (item.get("created_at") or "")[:10]
            if created >= since:
                atoms.append({
                    "title": item.get("title", "")[:60],
                    "category": item.get("category", ""),
                })
    return {"atom_count": len(atoms), "atoms": atoms}


def _collect_grove() -> dict:
    result = _mcp("grove_get_history", {
        "channel_name": "general",
        "limit": 50,
    }, timeout=10)
    if isinstance(result, dict) and result.get("error"):
        return {"message_count": 0, "topics": [], "error": result["error"]}
    messages = result.get("result", []) if isinstance(result, dict) else []
    since_dt = _now() - timedelta(days=_WEEK_DAYS)
    recent = []
    for m in messages:
        ts = m.get("created_at", "")
        try:
            if datetime.fromisoformat(ts.replace("Z", "+00:00")) >= since_dt:
                recent.append(m.get("content", "")[:80])
        except Exception:
            pass
    return {"message_count": len(recent), "topics": recent[:10]}


# ── Synthesis ──────────────────────────────────────────────────────────────────

_SYNTHESIS_PROMPT = """You are a system observing an engineer's work over the last 7 days.
Given the signals below, write a single paragraph (4-6 sentences) estimating their current heading:
what problem space are they moving toward, what they seem to be building toward, and what tension
or gap might emerge next week if the trajectory continues.

Be specific and grounded in the signals. Do not hedge excessively. Do not use em dashes.
Write in second person ("you are...").

--- SIGNALS ---

Git commits ({commit_count} this week):
{commits}

Think Map decisions ({map_count} confirmed, {draft_count} still open):
{decisions}

Open problems (draft Think Maps):
{open_problems}

Ledger observations ({obs_count} this week, {block_count} corrections/blocks):
{observations}

Session check-ins ({checkin_count}):
{checkins}

Upstream posts this week: {post_count}
Projects touched: {projects}

Latest handoff ({handoff_date}):
{handoff_summary}

Open threads from last handoff:
{open_threads}

KB atoms written this week ({atom_count}):
{atoms}

Grove activity: {grove_count} messages in general channel.
Topics: {grove_topics}

--- END SIGNALS ---

Write the heading estimate now. One paragraph only."""


def _synthesize(signals: dict) -> str:
    git = signals["git"]
    maps = signals["think_maps"]
    kb = signals["kb"]
    grove = signals["grove"]
    ledger = signals["ledger"]
    handoff = signals["handoff"]

    commits_text = "\n".join(f"  - {m}" for m in git["messages"][:15]) or "  (none)"
    decisions_text = "\n".join(
        f"  - {d['problem']} -> {d['decision']}" for d in maps["decisions"]
    ) or "  (none)"
    open_problems_text = "\n".join(f"  - {p}" for p in maps["open_problems"]) or "  (none)"
    atoms_text = "\n".join(
        f"  - [{a['category']}] {a['title']}" for a in kb["atoms"]
    ) or "  (none)"
    grove_topics = ", ".join(grove["topics"][:5]) or "none"
    obs_text = "\n".join(f"  - {o}" for o in ledger["observations"][:8]) or "  (none)"
    checkins_text = "\n".join(
        f"  - {c['summary']}" + (f" | next: {c['next']}" if c.get("next") else "")
        for c in ledger["checkins"]
    ) or "  (none)"
    projects_text = ", ".join(ledger["projects_touched"]) or "none"
    threads_text = "\n".join(f"  - {t}" for t in handoff["open_threads"]) or "  (none)"

    prompt = _SYNTHESIS_PROMPT.format(
        commit_count=git["commit_count"],
        commits=commits_text,
        map_count=maps["confirmed_count"],
        draft_count=maps["draft_count"],
        decisions=decisions_text,
        open_problems=open_problems_text,
        obs_count=ledger["observation_count"],
        block_count=ledger["block_count"],
        observations=obs_text,
        checkin_count=ledger["checkin_count"],
        checkins=checkins_text,
        post_count=ledger["post_count"],
        projects=projects_text,
        handoff_date=handoff["date"],
        handoff_summary=handoff["summary"][:300],
        open_threads=threads_text,
        atom_count=kb["atom_count"],
        atoms=atoms_text,
        grove_count=grove["message_count"],
        grove_topics=grove_topics,
    )

    result = _mcp("infer_chat", {
        "app_id": "hanuman",
        "message": prompt,
        "agent": "willow",
    }, timeout=60)

    if isinstance(result, dict):
        return (
            result.get("response")
            or result.get("content")
            or result.get("text")
            or result.get("message")
            or ""
        ).strip()
    return str(result).strip()


# ── KB write ───────────────────────────────────────────────────────────────────

def _write_atom(heading: str, signals: dict, week_start: str) -> dict:
    git = signals["git"]
    maps = signals["think_maps"]
    kb = signals["kb"]

    title = f"Dead Reckoning — Week of {week_start}"
    keywords = ["dead-reckoning", "heading", "trajectory", "weekly"]

    ledger = signals.get("ledger", {})
    summary = heading + (
        f"\n\nSignals: {git['commit_count']} commits, "
        f"{maps['confirmed_count']} Think Maps confirmed ({maps.get('draft_count', 0)} drafts), "
        f"{kb['atom_count']} KB atoms, "
        f"{ledger.get('observation_count', 0)} ledger observations, "
        f"{ledger.get('block_count', 0)} corrections."
    )

    result = _mcp("kb_ingest", {
        "app_id": "hanuman",
        "title": title,
        "summary": summary,
        "category": "dead_reckoning",
        "tier": "frontier",
        "source_type": "dead_reckoning",
        "source_id": f"dr-{week_start}",
        "keywords": keywords,
        "tags": ["dead-reckoning", "weekly"],
        "confidence": 0.7,
        "force": True,
    }, timeout=30)

    return result if isinstance(result, dict) else {"raw": str(result)}


# ── Main entry ─────────────────────────────────────────────────────────────────

def run(dry_run: bool = False) -> dict:
    """
    Collect signals, synthesise heading, write KB atom.
    Returns {heading, atom_id, signals_summary}.
    """
    week_start = (_now() - timedelta(days=_WEEK_DAYS)).strftime("%Y-%m-%d")

    print(f"[dead_reckoning] Collecting signals for week of {week_start}...")

    signals = {
        "git": _collect_git(),
        "think_maps": _collect_think_maps(),
        "kb": _collect_kb_atoms(),
        "grove": _collect_grove(),
        "ledger": _collect_ledger(),
        "handoff": _collect_handoffs(),
    }

    git = signals["git"]
    maps = signals["think_maps"]
    kb = signals["kb"]
    grove = signals["grove"]
    ledger = signals["ledger"]
    handoff = signals["handoff"]

    print(f"  git:         {git['commit_count']} commits")
    print(f"  think_maps:  {maps['confirmed_count']} confirmed, {maps['draft_count']} drafts")
    print(f"  kb atoms:    {kb['atom_count']} written this week")
    print(f"  ledger:      {ledger['observation_count']} observations, {ledger['block_count']} blocks, {ledger['post_count']} posts")
    print(f"  projects:    {', '.join(ledger['projects_touched']) or 'none'}")
    print(f"  handoff:     {handoff['date'] or 'none'}")
    print(f"  grove:       {grove['message_count']} messages")

    if git["commit_count"] == 0 and maps["confirmed_count"] == 0 and kb["atom_count"] == 0:
        print("  No signal this week — skipping synthesis.")
        return {"heading": "", "atom_id": "", "skipped": True}

    print("  Synthesising heading...")
    heading = _synthesize(signals)

    if not heading:
        print("  Synthesis returned empty — check infer_chat.")
        return {"heading": "", "atom_id": "", "error": "empty_synthesis"}

    print(f"\n--- HEADING ---\n{heading}\n---------------")

    if dry_run:
        print("  [dry_run] Skipping KB write.")
        return {"heading": heading, "atom_id": "", "dry_run": True}

    atom = _write_atom(heading, signals, week_start)
    atom_id = str(atom.get("id", atom.get("atom_id", "")))
    print(f"  KB atom: {atom_id or '(blocked/failed)'}")

    return {
        "heading": heading,
        "atom_id": atom_id,
        "week_start": week_start,
        "signals": {
            "commits": git["commit_count"],
            "think_maps": maps["confirmed_count"],
            "kb_atoms": kb["atom_count"],
            "grove_messages": grove["message_count"],
        },
    }
