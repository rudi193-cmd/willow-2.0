"""
persona.py — session persona picker and context injection.

State: ~/.willow/willow-2.0-active-persona
User personas: ~/.willow/user-personas.json  +  ~/.willow/personas/<name>.md
Wired from session_start (picker) and prompt_submit (selection + context).
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

STATE_FILE = Path.home() / ".willow" / "willow-2.0-active-persona"
DB_PATH = Path.home() / ".willow" / "willow-2.0.db"
USER_PERSONAS_FILE = Path.home() / ".willow" / "user-personas.json"

_CREATE_KEY = "__create__"



def _repo_root() -> Path:
    try:
        from willow.fylgja.project_env import repo_root

        return repo_root()
    except Exception:
        here = Path(__file__).resolve()
        return here.parent.parent.parent


def _persona_path(name: str) -> str:
    return str(_repo_root() / "willow" / "fylgja" / "personas" / f"{name}.md")


# Built-in personas — always available regardless of user config.
_BUILTIN_PERSONAS: dict[str, dict] = {
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

_BUILTIN_LIST = ["oakenscroll", "hanuman", "loki", "skirnir", "vishwakarma", "none"]

# Legacy aliases — kept so callers that imported PERSONAS/PERSONA_LIST directly still work.
PERSONAS = _BUILTIN_PERSONAS
PERSONA_LIST = _BUILTIN_LIST


def load_user_personas() -> dict[str, dict]:
    """Read ~/.willow/user-personas.json. Returns {} on missing or parse error."""
    if not USER_PERSONAS_FILE.exists():
        return {}
    try:
        data = json.loads(USER_PERSONAS_FILE.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    except Exception:
        return {}


def register_user_persona(key: str, label: str, desc: str, persona_md_path: str) -> bool:
    """
    Record a user persona in ~/.willow/user-personas.json after the agent has:
      1. Called agent_create MCP tool (which sets up ~/SAFE/Agents/<key>/ + PGP + manifest)
      2. Written the persona .md file to ~/SAFE/Agents/<key>/persona.md

    This function is called by the agent post-registration, not by the hook.
    persona_md_path should be the absolute path written by agent_create flow.
    """
    key = key.strip().lower().replace(" ", "_")
    if not key or key in _BUILTIN_PERSONAS:
        return False
    existing = load_user_personas()
    existing[key] = {
        "label": label,
        "desc": desc,
        "source": "file",
        "path": persona_md_path,
    }
    USER_PERSONAS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USER_PERSONAS_FILE.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return True


def get_personas() -> tuple[dict[str, dict], list[str]]:
    """
    Return (personas_dict, ordered_list) with user personas merged in before 'none'.
    The list never includes _CREATE_KEY — that's a UI action, not a persona.
    """
    user = load_user_personas()
    combined: dict[str, dict] = {}
    combined_list: list[str] = []
    for key in _BUILTIN_LIST:
        if key == "none":
            # Insert user personas just before "none"
            for ukey, uval in user.items():
                if ukey not in combined:
                    combined[ukey] = uval
                    combined_list.append(ukey)
        combined[key] = _BUILTIN_PERSONAS[key]
        combined_list.append(key)
    return combined, combined_list


def active_persona() -> str:
    if STATE_FILE.exists():
        name = STATE_FILE.read_text(encoding="utf-8").strip().lower()
        personas, _ = get_personas()
        if name in personas:
            return name
    return ""


def set_active_persona(name: str) -> bool:
    key = (name or "").strip().lower()
    personas, _ = get_personas()
    if key not in personas:
        return False
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(key + "\n", encoding="utf-8")
    return True


def render_picker(active: str = "") -> str:
    personas, persona_list = get_personas()
    bar = "━" * 54
    lines = [
        "[PERSONA — CONFIRM OR SWITCH BEFORE WORK BEGINS]",
        bar,
    ]
    for i, key in enumerate(persona_list, 1):
        p = personas[key]
        if key == active:
            lines.append(f"  {i}. {p['label']:<14} {p['desc']}  ← ACTIVE")
        else:
            lines.append(f"  {i}. {p['label']:<14} {p['desc']}")
    create_num = len(persona_list) + 1
    lines.append(f"  {create_num}. + Create new persona")
    lines.append(bar)
    if active:
        lines.append(
            f"  Active: {personas[active]['label']}. "
            "Reply with a number or name to switch, or continue."
        )
    else:
        lines.append(
            f"  No persona active. Reply with a number or name "
            f"(or '{len(persona_list)}' for none, '{create_num}' to create)."
        )
    return "\n".join(lines)


def render_status(active: str) -> str:
    personas, persona_list = get_personas()
    labels = []
    for i, key in enumerate(persona_list, 1):
        if key == active:
            labels.append(f"[{i}:{personas[key]['label']} ←]")
        else:
            labels.append(f"{i}:{personas[key]['label']}")
    return f"<persona> {' | '.join(labels)} | say \"switch to N\" to change </persona>"


def render_create_prompt() -> str:
    bar = "━" * 54
    return "\n".join([
        "[PERSONA — CREATE NEW]",
        bar,
        "  Creating a persona registers a new agent in the fleet.",
        "  The process:",
        "    1. Choose a short name  (e.g. mentor, analyst, coach)",
        "    2. Provide a one-line role description",
        "    3. agent_create MCP tool sets up ~/SAFE/Agents/<name>/ + PGP key + manifest",
        "    4. Write persona .md to ~/SAFE/Agents/<name>/persona.md",
        "    5. register_user_persona() records it in ~/.willow/user-personas.json",
        "    6. Persona appears in the picker next session.",
        "",
        "  Reply with:",
        "    name:  <short-key>",
        "    role:  <one-line description>",
        "    trust: WORKER | ENGINEER | OPERATOR  (default: WORKER)",
        "",
        "  Or describe the persona you want and I'll draft the content for you.",
        bar,
    ])



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
    personas, _ = get_personas()
    if not name or name not in personas:
        return ""
    p = personas[name]
    source = p["source"]
    if source == "seeds":
        return load_from_seeds(p["seed_ids"])
    if source == "file":
        return load_from_file(p["path"], p["label"])
    return ""


def parse_selection(prompt: str) -> str | None:
    """Return persona key (or _CREATE_KEY) if the user message is a persona pick/action."""
    _, persona_list = get_personas()
    text = (prompt or "").strip()
    if not text:
        return None
    lower = text.lower()

    # Numeric pick — includes the "create" slot at len(persona_list)+1
    if re.fullmatch(r"\d+", lower):
        idx = int(lower)
        if 1 <= idx <= len(persona_list):
            return persona_list[idx - 1]
        if idx == len(persona_list) + 1:
            return _CREATE_KEY

    # "create" keywords
    if re.search(r"\b(create|new persona|\+ create)\b", lower):
        return _CREATE_KEY

    # Named switch
    m = re.search(r"(?:switch\s+to\s+|persona[:\s]+|use\s+persona\s+)([a-z_]+)", lower)
    if m:
        personas, _ = get_personas()
        if m.group(1) in personas:
            return m.group(1)

    # Bare name match
    personas, _ = get_personas()
    if lower in personas and len(lower.split()) == 1:
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
        if choice == _CREATE_KEY:
            parts.append(render_create_prompt())
            return "\n".join(parts)
        if choice:
            set_active_persona(choice)
            active = choice
        # Always show the full picker on the first turn — unmissable, like the boot gate.
        parts.append(render_picker(active))
        parts.append(
            "[PERSONA-VISIBLE] Paste the PERSONA block above into your user-visible reply "
            "(markdown fenced block). Hook-only context is not shown in chat."
        )
    elif active:
        parts.append(render_status(active))

    if active and active != "none":
        context = load_persona(active)
        if context:
            parts.append(context)

    return "\n".join(parts)
