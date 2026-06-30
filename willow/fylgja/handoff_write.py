"""
Canonical session handoff markdown writer.

Agents should call write_session_handoff() at end of session so handoff_rebuild
indexes a file with YAML frontmatter at the path SessionStart expects.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from willow.fylgja.willow_home import willow_home
from willow.fylgja.handoff_project import resolve_handoff_project


def handoff_dir(agent: str) -> Path:
    return willow_home() / "handoffs" / agent


def next_session_filename(agent: str, suffix: str = "") -> str:
    """Return session_handoff-YYYY-MM-DD{sfx}_{agent}.md avoiding collisions."""
    # UTC is the canonical clock for all Willow artifacts — intentional, do NOT
    # localize. The harness reports "today" in local time, so this filename can be
    # one day ahead between ~18:00 local and midnight. That gap is correct; the
    # prompt_submit [CLOCK] line declares the relationship to agents each turn.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = f"session_handoff-{today}{suffix}_{agent}.md"
    dest = handoff_dir(agent)
    if not (dest / base).exists():
        return base
    for letter in "bcdefghijklmnopqrstuvwxyz":
        candidate = f"session_handoff-{today}{letter}_{agent}.md"
        if not (dest / candidate).exists():
            return candidate
    return base


def write_session_handoff(
    agent: str,
    body: str,
    *,
    project: str = "",
    branch: str = "",
    suffix: str = "",
) -> Path:
    """
    Write a session handoff markdown file with required YAML frontmatter.

    body: markdown starting with '# HANDOFF:' or '# SESSION HANDOFF' — frontmatter prepended.
    """
    project_id = (project or resolve_handoff_project() or "willow-2.0").strip()
    dest_dir = handoff_dir(agent)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = next_session_filename(agent, suffix)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Extract the session letter from the filename (e.g. "2026-05-26f" from "session_handoff-2026-05-26f_hanuman.md")
    import re as _re
    _m = _re.search(r"session_handoff-(\d{4}-\d{2}-\d{2}[a-z]?)_", filename)
    session_id = _m.group(1) if _m else today
    frontmatter = "\n".join([
        "---",
        f"agent: {agent}",
        f"date: {today}",
        f"session: {session_id}",
        "runtime: claude-code",
        "format: v2",
        f"project: {project_id}",
        *( [f"branch: {branch}"] if branch else [] ),
        "---",
        "",
    ])
    text = body.lstrip()
    if not text.startswith("---"):
        text = frontmatter + text
    elif not re.search(r"^agent:\s*", text, re.MULTILINE):
        # Body has frontmatter but missing agent — prepend our block after first ---
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = f"---\nagent: {agent}\ndate: {today}\nproject: {project_id}\n---{parts[2]}"
    path = dest_dir / filename
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return path
