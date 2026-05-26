"""
Canonical session handoff markdown writer.

Agents should call write_session_handoff() at end of session so handoff_rebuild
indexes a file with YAML frontmatter at the path SessionStart expects.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path


def handoff_dir(agent: str) -> Path:
    return Path.home() / ".willow" / "handoffs" / agent


def next_session_filename(agent: str, suffix: str = "") -> str:
    """Return session_handoff-YYYY-MM-DD{sfx}_{agent}.md avoiding collisions."""
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
    project: str = "willow-2.0",
    branch: str = "",
    suffix: str = "",
) -> Path:
    """
    Write a session handoff markdown file with required YAML frontmatter.

    body: markdown starting with '# HANDOFF:' or '# SESSION HANDOFF' — frontmatter prepended.
    """
    dest_dir = handoff_dir(agent)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = next_session_filename(agent, suffix)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    frontmatter = "\n".join([
        "---",
        f"agent: {agent}",
        f"date: {today}",
        f"project: {project}",
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
            text = f"---\nagent: {agent}\ndate: {today}\nproject: {project}\n---{parts[2]}"
    path = dest_dir / filename
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return path
