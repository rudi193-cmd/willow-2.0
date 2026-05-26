"""
persona.py — session persona picker and context injection.

State: ~/.willow/willow-2.0-active-persona
Wired from session_start (picker) and prompt_submit (selection + context).
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

STATE_FILE = Path.home() / ".willow" / "willow-2.0-active-persona"
DB_PATH = Path.home() / ".willow" / "willow-2.0.db"


def _repo_root() -> Path:
    try:
        from willow.fylgja.project_env import repo_root

        return repo_root()
    except Exception:
        here = Path(__file__).resolve()
        return here.parent.parent.parent


def _persona_path(name: str) -> str:
    return str(_repo_root() / "willow" / "fylgja" / "personas" / f"{name}.md")


PERSONAS = {
    "oakenscroll": {
        "label": "Oakenscroll",
        "desc": "Professor, Dept. of Numerical Ethics & Accidental Cosmology, UTETY",
        "source": "seeds",
        "seed_ids": ["OAKENSCROLL_SEED_v1", "OAKENSCROLL_SEED_v2", "OAKENSCROLL_SEED_v3"],
    },
    "hanuman": {
        "label": "Hanuman",
        "desc": "Builder. Fleet coordinator. Claude Code CLI.",
        "source": "file",
        "path": _persona_path("hanuman"),
    },
    "loki": {
        "label": "Loki",
        "desc": "The one they didn't plan for. Fleet accountant.",
        "source": "file",
        "path": _persona_path("loki"),
    },
    "skirnir": {
        "label": "Skirnir",
        "desc": "Emissary. Gate-witness.",
        "source": "file",
        "path": _persona_path("skirnir"),
    },
    "vishwakarma": {
        "label": "Vishwakarma",
        "desc": "Divine architect. Builder of the SAFE App Store.",
        "source": "file",
        "path": _persona_path("vishwakarma"),
    },
    "none": {
        "label": "None",
        "desc": "Blank slate — no persona injected.",
        "source": "none",
    },
}

PERSONA_LIST = ["oakenscroll", "hanuman", "loki", "skirnir", "vishwakarma", "none"]


def active_persona() -> str:
    if STATE_FILE.exists():
        name = STATE_FILE.read_text(encoding="utf-8").strip().lower()
        if name in PERSONAS:
            return name
    return ""


def set_active_persona(name: str) -> bool:
    key = (name or "").strip().lower()
    if key not in PERSONAS:
        return False
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(key + "\n", encoding="utf-8")
    return True


def render_picker(active: str = "") -> str:
    lines = ["[PERSONA]", "<persona-picker>"]
    for i, key in enumerate(PERSONA_LIST, 1):
        p = PERSONAS[key]
        marker = " ← active" if key == active else ""
        lines.append(f"  {i}. {p['label']}{marker} — {p['desc']}")
    lines.append("")
    if active:
        lines.append(f"  Active: {PERSONAS[active]['label']}. Reply with a number or name to switch.")
    else:
        lines.append("  No persona active. Reply with a number or name (or 'none').")
    lines.append("</persona-picker>")
    return "\n".join(lines)


def render_status(active: str) -> str:
    labels = []
    for i, key in enumerate(PERSONA_LIST, 1):
        if key == active:
            labels.append(f"[{i}:{PERSONAS[key]['label']} ←]")
        else:
            labels.append(f"{i}:{PERSONAS[key]['label']}")
    return f"<persona> {' | '.join(labels)} | say \"switch to N\" to change </persona>"


def load_from_seeds(seed_ids: list[str]) -> str:
    if not DB_PATH.exists():
        print("persona: DB not found", file=sys.stderr)
        return ""
    conn = sqlite3.connect(str(DB_PATH))
    lines = ["# Persona — Session Injection", ""]
    for sid in seed_ids:
        cur = conn.execute(
            "SELECT section, body FROM seed_sections WHERE seed_id = ? ORDER BY section",
            (sid,),
        )
        rows = cur.fetchall()
        if not rows:
            print(f"persona: {sid} not found in seed_sections — skipping", file=sys.stderr)
            continue
        lines.append(f"## {sid}")
        for section, body in rows:
            lines.append(f"### {section}")
            lines.append("```json")
            lines.append(body)
            lines.append("```")
            lines.append("")
    conn.close()
    return "\n".join(lines)


def load_from_file(path: str, label: str) -> str:
    p = Path(path)
    if not p.exists():
        print(f"persona: file not found at {path}", file=sys.stderr)
        return ""
    return f"# Persona — {label}\n\n{p.read_text(encoding='utf-8')}"


def load_persona(name: str) -> str:
    if not name or name not in PERSONAS:
        return ""
    p = PERSONAS[name]
    source = p["source"]
    if source == "seeds":
        return load_from_seeds(p["seed_ids"])
    if source == "file":
        return load_from_file(p["path"], p["label"])
    return ""


def parse_selection(prompt: str) -> str | None:
    """Return persona key if the user message is a persona pick."""
    text = (prompt or "").strip()
    if not text:
        return None
    lower = text.lower()

    if re.fullmatch(r"\d+", lower):
        idx = int(lower)
        if 1 <= idx <= len(PERSONA_LIST):
            return PERSONA_LIST[idx - 1]

    m = re.search(r"(?:switch\s+to\s+|persona[:\s]+|use\s+persona\s+)([a-z]+)", lower)
    if m and m.group(1) in PERSONAS:
        return m.group(1)

    if lower in PERSONAS and len(lower.split()) == 1:
        return lower

    return None


def anchor_lines() -> str:
    """SessionStart anchor: always show the picker."""
    return render_picker(active_persona())


def prompt_submit_block(*, is_first: bool, prompt: str) -> str:
    """Build persona lines for beforeSubmitPrompt."""
    parts: list[str] = []
    active = active_persona()

    if is_first:
        choice = parse_selection(prompt)
        if choice:
            set_active_persona(choice)
            active = choice
            label = PERSONAS[active]["label"]
            parts.append(f"[PERSONA] Selected: {label}")
        elif not active:
            parts.append("[PERSONA] No persona active — pick a number or name from the SessionStart list.")
    elif active:
        parts.append(render_status(active))

    if active and active != "none":
        context = load_persona(active)
        if context:
            parts.append(context)

    return "\n".join(parts)
