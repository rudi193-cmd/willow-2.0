#!/usr/bin/env python3
# b17: PER20  ΔΣ=42
"""
persona.py — session persona injector for willow-2.0.

Every prompt: if no persona set, shows full picker.
              if persona set, shows compact status line + injects context.

State stored in ~/.willow/willow-2.0-active-persona.
To switch: tell the LLM the number or name; it writes the state file.
Wire as second UserPromptSubmit hook in .claude/settings.json.
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH    = Path.home() / ".willow" / "willow-2.0.db"
STATE_FILE = Path.home() / ".willow" / "willow-2.0-active-persona"

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
        "path": "/home/example/willow-1.9/CLAUDE.md",
    },
    "loki": {
        "label": "Loki",
        "desc": "The one they didn't plan for. Fleet accountant.",
        "source": "file",
        "path": "/home/example/github/CLAUDE.md",
    },
    "skirnir": {
        "label": "Skirnir",
        "desc": "Emissary. Gate-witness.",
        "source": "file",
        "path": "/home/example/github/skirnir/CLAUDE.md",
    },
    "vishwakarma": {
        "label": "Vishwakarma",
        "desc": "Divine architect. Builder of the SAFE App Store.",
        "source": "file",
        "path": "/home/example/github/safe-app-store/CLAUDE.md",
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
        name = STATE_FILE.read_text().strip().lower()
        if name in PERSONAS:
            return name
    return ""


def render_picker(active: str) -> str:
    lines = ["<persona-picker>"]
    for i, key in enumerate(PERSONA_LIST, 1):
        p = PERSONAS[key]
        marker = " ←" if key == active else ""
        lines.append(f"  {i}. {p['label']}{marker} — {p['desc']}")
    lines.append("")
    if active:
        lines.append(f"  Active: {active}. To switch, tell me the number or name.")
    else:
        lines.append("  No persona active. Tell me a number or name to pick one.")
    lines.append("</persona-picker>")
    return "\n".join(lines)


def render_status(active: str) -> str:
    labels = []
    for i, key in enumerate(PERSONA_LIST, 1):
        marker = f"[{i}:{PERSONAS[key]['label']} ←]" if key == active else f"{i}:{PERSONAS[key]['label']}"
        labels.append(marker)
    return f"<persona> {' | '.join(labels)} | say \"switch to N\" to change </persona>"


def load_from_seeds(seed_ids: list) -> str:
    if not DB_PATH.exists():
        print("persona.py: DB not found", file=sys.stderr)
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
            print(f"persona.py: {sid} not found in seed_sections — skipping", file=sys.stderr)
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
        print(f"persona.py: CLAUDE.md not found at {path}", file=sys.stderr)
        return ""
    return f"# Persona — {label}\n\n{p.read_text()}"


def load_persona(name: str) -> str:
    if not name or name not in PERSONAS:
        return ""
    p = PERSONAS[name]
    source = p["source"]
    if source == "seeds":
        return load_from_seeds(p["seed_ids"])
    if source == "file":
        return load_from_file(p["path"], p["label"])
    return ""  # "none"


def main() -> int:
    active = active_persona()
    parts  = []

    if not active:
        parts.append(render_picker(active))
    else:
        parts.append(render_status(active))
        context = load_persona(active)
        if context:
            parts.append(context)

    print("\n".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
