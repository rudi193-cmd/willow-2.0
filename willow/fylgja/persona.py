"""
persona.py — session persona picker and context injection.

State: $WILLOW_HOME/willow-2.0-active-persona
User personas: $WILLOW_HOME/user-personas.json  +  $WILLOW_HOME/personas/<name>.md
Wired from session_start (picker) and prompt_submit (selection + context).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

from willow.fylgja.willow_home import willow_home

_HOME = willow_home()
STATE_FILE = _HOME / "willow-2.0-active-persona"
DB_PATH = _HOME / "willow-2.0.db"
USER_PERSONAS_FILE = _HOME / "user-personas.json"

_CREATE_KEY = "__create__"


def _state_project_file() -> Path:
    """Companion to STATE_FILE recording the project an explicit pick was made in.

    Computed from STATE_FILE at call time so tests that monkeypatch STATE_FILE
    redirect this file too.
    """
    return STATE_FILE.parent / (STATE_FILE.name + ".project")


def _project_personas_file() -> Path:
    """config/project_personas.json — maps a project key to a default persona."""
    return _repo_root() / "willow" / "fylgja" / "config" / "project_personas.json"


def current_project_key() -> str:
    """Best-effort name of the project being worked on (not the willow code repo).

    Prefers WILLOW_HANDOFF_PROJECT (set per-project by mcp sync), then the
    workspace root directory name. Empty string when neither resolves.
    """
    proj = os.environ.get("WILLOW_HANDOFF_PROJECT", "").strip()
    if proj:
        return proj
    try:
        from willow.fylgja.project_env import workspace_root

        ws = workspace_root()
        if ws is not None:
            return ws.name
    except Exception:
        pass
    return ""


def _project_binding_info(project: str = "") -> tuple[str, bool]:
    """(persona_key, locked) bound to the current (or given) project.

    A binding value is either a plain persona-key string (unlocked default) or
    an object {"persona": <key>, "locked": true} — a hard lock: explicit picks
    in that project are refused and the binding always wins.
    Returns ("", False) when there is no valid binding.
    """
    proj = (project or current_project_key()).strip()
    if not proj:
        return "", False
    path = _project_personas_file()
    if not path.exists():
        return "", False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        bindings = data.get("bindings", {}) if isinstance(data, dict) else {}
    except Exception:
        return "", False
    raw = bindings.get(proj, "")
    locked = False
    if isinstance(raw, dict):
        locked = bool(raw.get("locked"))
        raw = raw.get("persona", "")
    key = str(raw).strip().lower()
    if not key:
        return "", False
    personas, _ = get_personas()
    if key not in personas:
        return "", False
    return key, locked


def project_persona_binding(project: str = "") -> str:
    """Persona key bound to the current (or given) project, or '' if none/invalid."""
    return _project_binding_info(project)[0]


def project_persona_locked(project: str = "") -> bool:
    """True when the project's binding is a hard lock (picks refused)."""
    return _project_binding_info(project)[1]



def _repo_root() -> Path:
    try:
        from willow.fylgja.project_env import repo_root

        return repo_root()
    except Exception:
        here = Path(__file__).resolve()
        return here.parent.parent.parent


def _persona_path(name: str) -> str:
    return str(_repo_root() / "willow" / "fylgja" / "personas" / f"{name}.md")


def persona_boot_overlay_path(name: str) -> Path | None:
    """Resolve optional boot-time persona overlay: willow/fylgja/skills/{persona}-boot.md."""
    key = (name or "").strip().lower()
    if not key or key == "none":
        return None
    path = _repo_root() / "willow" / "fylgja" / "skills" / f"{key}-boot.md"
    return path if path.is_file() else None


# Built-in personas — always available regardless of user config.
_BUILTIN_PERSONAS: dict[str, dict] = {
    "oakenscroll": {
        "label": "Oakenscroll",
        "desc": "Professor, Dept. of Numerical Ethics & Accidental Cosmology, UTETY",
        "source": "file",
        "path": _persona_path("oakenscroll"),
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
    "jeles": {
        "label": "Jeles",
        "desc": "Head Librarian at UTETY. Retrieval, citation, and sourced synthesis.",
        "source": "file",
        "path": _persona_path("jeles"),
    },
    "ada": {
        "label": "Ada",
        "desc": "Systems Administrator of UTETY. Keeper of the Quiet Uptime — monitor-first.",
        "source": "file",
        "path": _persona_path("ada"),
        # Voice overlay only — Ada is a UTETY professor, NOT a fleet agent id.
        # Marked so the active-agent collision guard does not treat her as one.
        "fleet_agent": False,
    },
    "none": {
        "label": "None",
        "desc": "Blank slate — no persona injected.",
        "source": "none",
    },
}

_BUILTIN_LIST = ["oakenscroll", "hanuman", "loki", "skirnir", "vishwakarma", "jeles", "ada", "none"]

# Built-in persona keys that double as fleet agent ids — easy to confuse with active-agent.
# Personas explicitly flagged fleet_agent=False (e.g. Ada, a UTETY voice persona) are excluded
# so the collision guard does not warn/block when they differ from the active fleet agent.
_FLEET_NAMED_PERSONAS = frozenset(
    k for k, v in _BUILTIN_PERSONAS.items()
    if k != "none" and v.get("fleet_agent", True)
)

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


def persona_agent_block_mode() -> str:
    """off | warn | strict — when a fleet-named persona != active-agent."""
    raw = os.environ.get("WILLOW_PERSONA_AGENT_BLOCK", "warn").strip().lower()
    if raw in ("off", "0", "false", "no"):
        return "off"
    if raw in ("strict", "enforce", "block"):
        return "strict"
    return "warn"


def fleet_agent_id() -> str:
    """Canonical fleet agent (active-agent, then WILLOW_AGENT_NAME, then hook resolution)."""
    try:
        from willow.fylgja.project_env import read_active_agent, repo_root, resolve_agent_name

        root = repo_root()
        active = read_active_agent(root)
        if active:
            return active.strip().lower()
        try:
            return resolve_agent_name(root).strip().lower()
        except EnvironmentError:
            pass
    except Exception:
        pass
    return os.environ.get("WILLOW_AGENT_NAME", "").strip().lower()


def persona_identity_banner(persona_key: str, *, switched: bool = False) -> str:
    """Clarify persona overlay vs fleet MCP/Grove/SOIL identity."""
    personas, _ = get_personas()
    label = personas.get(persona_key, {}).get("label", persona_key.capitalize())
    fleet = fleet_agent_id() or "(unset)"
    verb = "Persona changed to" if switched else "Persona active"
    return "\n".join([
        f"[PERSONA-IDENTITY] {verb} **{label}** (voice overlay only).",
        f"[PERSONA-IDENTITY] Fleet identity remains **{fleet}** "
        "(`.willow/active-agent` / `WILLOW_AGENT_NAME`).",
        "[PERSONA-IDENTITY] Persona does not change MCP `app_id`, Grove sender, or SOIL namespace.",
        "[PERSONA-IDENTITY] Switch fleet agent: `./willow agents active <id> --install`",
    ])


def check_persona_fleet_collision(persona_key: str) -> tuple[bool, str | None]:
    """
    Warn or block when user picks a persona whose key matches a fleet agent id
    but active-agent is different (looks like an agent switch, is not).
    Returns (allowed, message).
    """
    mode = persona_agent_block_mode()
    if mode == "off" or persona_key in ("", "none") or persona_key not in _FLEET_NAMED_PERSONAS:
        return True, None
    fleet = fleet_agent_id()
    if not fleet or persona_key == fleet:
        return True, None
    msg = (
        f"Persona {persona_key!r} matches a fleet agent id but active-agent is {fleet!r}. "
        "This changes voice only — not MCP app_id, Grove sender, or SOIL namespace."
    )
    if mode == "strict":
        return False, msg
    return True, msg


def active_persona() -> str:
    """Resolve the active persona.

    Precedence:
      0. A *locked* project binding — always wins; picks in that project are
         refused by set_active_persona().
      1. An explicit pick made *in the current project* (global state whose
         recorded project matches) — so switching inside a bound project sticks.
      2. The project's configured persona binding (config/project_personas.json).
      3. The global explicit pick (legacy behavior for unbound projects).
    """
    personas, _ = get_personas()

    state = ""
    if STATE_FILE.exists():
        state = STATE_FILE.read_text(encoding="utf-8").strip().lower()
    if state not in personas:
        state = ""

    proj = current_project_key()
    binding, locked = _project_binding_info(proj)

    # 0. Hard lock — the binding is the persona, no override.
    if binding and locked:
        return binding

    state_proj = ""
    spf = _state_project_file()
    if spf.exists():
        state_proj = spf.read_text(encoding="utf-8").strip()

    # 1. Explicit pick made in this same project wins.
    if state and proj and state_proj == proj:
        return state

    # 2. Project binding is the default for bound projects.
    if binding:
        return binding

    # 3. Fall back to the global explicit pick.
    return state


def set_active_persona(name: str) -> bool:
    key = (name or "").strip().lower()
    personas, _ = get_personas()
    if key not in personas:
        return False
    binding, locked = _project_binding_info()
    if locked and binding and key != binding:
        return False
    allowed, _msg = check_persona_fleet_collision(key)
    if not allowed:
        return False
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(key + "\n", encoding="utf-8")
    # Record which project this explicit pick was made in, so a project binding
    # does not silently override a deliberate in-project switch.
    _state_project_file().write_text(current_project_key() + "\n", encoding="utf-8")
    return True


def render_picker(active: str = "", *, blocking: bool = False) -> str:
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
    fleet = fleet_agent_id()
    if fleet:
        lines.append(
            f"  Fleet identity: **{fleet}** (persona is voice only — does not switch agent)"
        )
    binding, locked = _project_binding_info()
    if locked and binding:
        lines.append(
            f"  🔒 Locked: this project always speaks as **{personas[binding]['label']}** "
            "(project_personas.json)."
        )
    if active:
        if blocking:
            lines.append(
                f"  Active: **{personas[active]['label']}** — "
                "reply with a number to switch, or say **go** to continue."
            )
        else:
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
        content = load_from_seeds(p["seed_ids"])
        if content:
            return content
        # Fallback to .md file if seeds unavailable (seed_sections table missing etc.)
        fallback = _persona_path(name)
        if Path(fallback).exists():
            return load_from_file(fallback, p["label"])
        return ""
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

    # Confirm active persona without re-picking
    if lower in ("continue", "go", "yes", "ok", "proceed", "same"):
        active = active_persona()
        if active:
            return active

    return None


def anchor_lines() -> str:
    """SessionStart anchor: always show the picker."""
    return render_picker(active_persona())


def prompt_submit_block(*, is_first: bool, prompt: str, session_id: str = "") -> str:
    """Build persona lines for beforeSubmitPrompt."""
    from core.boot_gate import mark_persona_ready

    parts: list[str] = []
    active = active_persona()

    if is_first:
        choice = parse_selection(prompt)
        binding, locked = _project_binding_info()
        if locked and binding and not choice:
            set_active_persona(binding)
            mark_persona_ready(session_id=session_id)
            active = binding
            parts.append(render_picker(active, blocking=False))
            parts.append(
                f"[PERSONA-LOCK] Project locked to {binding!r} — persona-ready sentinel written."
            )
            parts.append(persona_identity_banner(binding, switched=False))
            context = load_persona(binding)
            if context:
                parts.append(context)
            return "\n".join(parts)
        if choice == _CREATE_KEY:
            parts.append(render_create_prompt())
            return "\n".join(parts)
        if choice:
            allowed, collision_msg = check_persona_fleet_collision(choice)
            if not allowed:
                parts.append(render_picker(active, blocking=True))
                parts.append(
                    f"[PERSONA-BLOCK] {collision_msg}\n"
                    "[PERSONA-BLOCK] Run `./willow agents active <id> --install` to switch fleet agent."
                )
                return "\n".join(parts)
            if not set_active_persona(choice):
                parts.append(render_picker(active, blocking=True))
                binding, locked = _project_binding_info()
                if locked and binding and choice != binding:
                    parts.append(
                        f"[PERSONA-LOCK] This project is locked to persona {binding!r} "
                        "(config/project_personas.json). Picks are refused here — "
                        "edit the binding to change it."
                    )
                else:
                    parts.append("[PERSONA-BLOCK] Could not set persona — invalid choice.")
                return "\n".join(parts)
            active = choice
            switched = True
            mark_persona_ready(session_id=session_id)
            parts.append(persona_identity_banner(choice, switched=switched))
            if collision_msg:
                parts.append(f"[PERSONA-WARN] {collision_msg}")
            # Choice confirmed — show picker and proceed to boot
            parts.append(render_picker(active, blocking=False))
            parts.append(
                "[PERSONA-VISIBLE] Paste the PERSONA block above into your user-visible reply "
                "(markdown fenced block). Include the PERSONA-IDENTITY lines. "
                "Persona confirmed — proceed with boot."
            )
        else:
            # No selection in this message — gate: show picker, stop, wait for user
            parts.append(render_picker(active, blocking=True))
            personas, _ = get_personas()
            label = personas.get(active, {}).get("label", active.capitalize()) if active else "None"
            parts.append(
                f"[PERSONA-GATE] No persona confirmed this session yet. Currently active: {label}. "
                "Picker is shown above — reply with a number, name, or 'continue' to confirm. "
                "Until persona-ready, only persona boot files are readable; MCP unlocks after confirm."
            )
            return "\n".join(parts)
    elif active:
        parts.append(render_status(active))
        parts.append(persona_identity_banner(active, switched=False))

    if is_first and active and active != "none":
        context = load_persona(active)
        if context:
            parts.append(context)

    return "\n".join(parts)
