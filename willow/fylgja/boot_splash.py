"""
Boot splash — runs as a SessionStart hook command.
Outputs rich ANSI art to stderr (stdout is reserved for hook runner output).
Persona-aware: reads willow-2.0-active-persona and dispatches to the right design.
Fails silently if pyfiglet/rich are unavailable.
"""
import os
import sys
import subprocess

VENV_PYTHON = os.path.expanduser(
    "~/github/willow-2.0/.venv-dev/bin/python3"
)
PERSONA_FILE = os.path.expanduser(
    "~/github/.willow/willow-2.0-active-persona"
)

# Per-persona design tokens
PERSONAS = {
    "skirnir": {
        "wordmark": "SKIRNIR",
        "font": "doom",
        "tagline": "emissary  ·  gate-witness",
        "c_gate":   "#3a6070",
        "c_word":   "#8ab8cc",
        "c_dim":    "#4a6878",
        "c_accent": "#b0cfd8",
        "c_label":  "#506878",
    },
}


def _active_persona():
    try:
        return open(PERSONA_FILE).read().strip().lower()
    except OSError:
        return ""


def _branch():
    try:
        return subprocess.getoutput(
            "git -C ~/github/willow-2.0 branch --show-current 2>/dev/null"
        ) or "unknown"
    except Exception:
        return "unknown"


def render(persona_key: str) -> None:
    cfg = PERSONAS.get(persona_key)
    if not cfg:
        return

    try:
        import pyfiglet
        from rich.console import Console
        from rich.text import Text
        from rich.rule import Rule
    except ImportError:
        return

    agent = os.environ.get("WILLOW_AGENT_NAME", "willow")
    branch = _branch()
    try:
        tty = open("/dev/tty", "w")
    except OSError:
        tty = sys.stderr
    console = Console(file=tty, width=100)

    wordmark = Text(
        pyfiglet.figlet_format(cfg["wordmark"], font=cfg["font"]),
        style=f"bold {cfg['c_word']}",
    )

    status = Text()
    status.append("◈ ", style=cfg["c_dim"])
    for label, val, vstyle in [
        ("agent",   agent,        cfg["c_accent"]),
        ("persona", persona_key,  cfg["c_word"]),
        ("branch",  branch,       cfg["c_dim"]),
    ]:
        status.append(f"{label} ", style=cfg["c_label"])
        status.append(val, style=vstyle)
        status.append("  ·  ", style=cfg["c_gate"])
    status.append("ΔΣ=42", style=cfg["c_word"])

    console.print()
    console.print(Rule(style=cfg["c_gate"]))
    console.print()
    console.print(wordmark, justify="center")
    console.print(
        Text(cfg["tagline"], style=f"italic {cfg['c_dim']}"), justify="center"
    )
    console.print()
    console.print(Rule(style=cfg["c_gate"]))
    console.print(status, justify="center")
    console.print(Rule(style=cfg["c_gate"]))
    console.print()


if __name__ == "__main__":
    render(_active_persona())
