"""
Status strip — fires on UserPromptSubmit.
Renders a single threshold line to /dev/tty: agent · persona · branch · git diff · ctx remaining.
Persona-aware: reads the PERSONAS registry and applies the active persona's palette.
Fails silently if any dependency is missing.
"""
import os
import sys
import json
import subprocess

PERSONA_FILE = os.path.expanduser("~/github/.willow/willow-2.0-active-persona")

PERSONAS = {
    "skirnir": {
        "c_rule":   "#3a6070",
        "c_anchor": "#8ab8cc",
        "c_dim":    "#4a6878",
        "c_plus":   "#5a9a7a",
        "c_minus":  "#9a5a5a",
        "c_ctx":    "#6a8898",
        "symbol":   "◈",
    },
}

CTX_LIMIT = 200_000  # tokens (Sonnet / Claude Max)


def _run(cmd):
    try:
        return subprocess.getoutput(cmd).strip()
    except Exception:
        return ""


def _active_persona():
    try:
        return open(PERSONA_FILE).read().strip().lower()
    except OSError:
        return ""


def _git_stats():
    """Return (files_changed, insertions, deletions) from working tree + index."""
    raw = _run("git diff --shortstat HEAD 2>/dev/null")
    if not raw:
        raw = _run("git diff --shortstat 2>/dev/null")
    files = ins = dels = 0
    import re
    m = re.search(r"(\d+) file", raw)
    if m:
        files = int(m.group(1))
    m = re.search(r"(\d+) insertion", raw)
    if m:
        ins = int(m.group(1))
    m = re.search(r"(\d+) deletion", raw)
    if m:
        dels = int(m.group(1))
    return files, ins, dels


def _ctx_remaining():
    """Estimate remaining context tokens from stdin payload size."""
    try:
        payload = sys.stdin.read()
        used = len(payload) // 4
        remaining = max(0, CTX_LIMIT - used)
        if remaining >= 1000:
            return f"~{remaining // 1000}k ctx"
        return f"~{remaining} ctx"
    except Exception:
        return ""


def render(persona_key: str, ctx_str: str) -> None:
    cfg = PERSONAS.get(persona_key)
    if not cfg:
        return

    try:
        from rich.console import Console
        from rich.text import Text
    except ImportError:
        return

    try:
        tty = open("/dev/tty", "w")
    except OSError:
        tty = sys.stderr

    console = Console(file=tty, width=100)

    agent  = os.environ.get("WILLOW_AGENT_NAME", "willow")
    branch = _run("git branch --show-current 2>/dev/null") or "unknown"
    files, ins, dels = _git_stats()

    line = Text()
    line.append(f" {cfg['symbol']}  ", style=cfg["c_anchor"])
    line.append(f"{agent}", style=cfg["c_anchor"])
    line.append("  ·  ", style=cfg["c_rule"])
    line.append(f"{persona_key}", style=cfg["c_anchor"])
    line.append("  ·  ", style=cfg["c_rule"])
    line.append(f"{branch}", style=cfg["c_dim"])

    if files:
        line.append("  ·  ", style=cfg["c_rule"])
        line.append(f"{files}f", style=cfg["c_dim"])
        line.append(f" +{ins}", style=cfg["c_plus"])
        line.append(f" −{dels}", style=cfg["c_minus"])

    if ctx_str:
        line.append("  ·  ", style=cfg["c_rule"])
        line.append(ctx_str, style=cfg["c_ctx"])

    line.append("  ·  ", style=cfg["c_rule"])
    line.append("ΔΣ=42", style=cfg["c_anchor"])

    from rich.rule import Rule
    console.print(Rule(characters="─", style=cfg["c_rule"]))
    console.print(line, justify="center")
    console.print(Rule(characters="─", style=cfg["c_rule"]))


if __name__ == "__main__":
    persona = _active_persona()
    ctx_str = _ctx_remaining()
    render(persona, ctx_str)
