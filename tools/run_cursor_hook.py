#!/usr/bin/env python3
"""
Cursor hook adapter: translate Cursor hook I/O to Fylgja event modules.

Runs the same willow.fylgja.events.* handlers Claude Code uses, but maps
stdin/stdout between Cursor hooks.json and Claude hookSpecificOutput formats.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from run_fylgja_hook import _load_mcp_env, _repo_root


def _read_stdin() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _cursor_to_claude(module: str, payload: dict) -> dict:
    event = payload.get("hook_event_name", "")

    if module.endswith("session_start"):
        return {
            "session_id": payload.get("session_id") or payload.get("conversation_id", ""),
            "source": payload.get("source", "startup"),
        }

    if module.endswith("prompt_submit"):
        return {
            "session_id": payload.get("conversation_id") or payload.get("session_id", "unknown"),
            "prompt": payload.get("prompt", ""),
        }

    if module.endswith("pre_tool"):
        if event == "beforeMCPExecution":
            server = payload.get("server", "willow")
            tool = payload.get("tool_name", "")
            tool_input = payload.get("tool_input")
            if isinstance(tool_input, str):
                try:
                    tool_input = json.loads(tool_input)
                except json.JSONDecodeError:
                    tool_input = {}
            if not isinstance(tool_input, dict):
                tool_input = {}
            return {
                "session_id": payload.get("conversation_id", ""),
                "tool_name": f"mcp__{server}__{tool}",
                "tool_input": tool_input,
            }

        command = payload.get("command", "")
        return {
            "session_id": payload.get("conversation_id", ""),
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }

    if module.endswith("stop"):
        return {
            "session_id": payload.get("conversation_id", ""),
            "status": payload.get("status", "completed"),
        }

    return payload


def _claude_to_cursor(module: str, stdout: str, returncode: int) -> dict:
    text = stdout.strip()
    if not text:
        return {}

    if module.endswith("session_start"):
        try:
            data = json.loads(text)
            ctx = data.get("hookSpecificOutput", {}).get("additionalContext", "")
            if ctx:
                return {"additional_context": ctx}
        except json.JSONDecodeError:
            pass
        return {"additional_context": text}

    if module.endswith("prompt_submit"):
        if text.startswith("{"):
            try:
                data = json.loads(text)
                ctx = data.get("hookSpecificOutput", {}).get("additionalContext", "")
                if ctx:
                    return {"additional_context": ctx}
            except json.JSONDecodeError:
                pass
        return {"additional_context": text}

    if module.endswith("pre_tool"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {"permission": "allow", "agent_message": text[:500]}

        if data.get("decision") == "block":
            reason = data.get("reason", "Blocked by Willow pre_tool hook.")
            return {
                "continue": False,
                "permission": "deny",
                "user_message": reason[:300],
                "agent_message": reason[:500],
            }
        return {"permission": "allow"}

    return {}


def _run_module(module: str, payload: dict) -> tuple[str, int]:
    repo = _repo_root()
    merged = os.environ.copy()
    for k, v in _load_mcp_env(repo).items():
        merged.setdefault(k, v)
    if not (merged.get("WILLOW_AGENT_NAME") or "").strip():
        merged["WILLOW_AGENT_NAME"] = "heimdallr"
    merged["PYTHONPATH"] = str(repo)

    venv_python = repo / ".venv-dev" / "bin" / "python3"
    py = str(venv_python) if venv_python.is_file() else sys.executable
    claude_payload = _cursor_to_claude(module, payload)

    proc = subprocess.run(
        [py, "-m", module],
        input=json.dumps(claude_payload),
        capture_output=True,
        text=True,
        env=merged,
        cwd=str(repo),
    )
    stdout = proc.stdout or ""
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return stdout, proc.returncode


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: run_cursor_hook.py <python.module.to.run>", file=sys.stderr)
        sys.exit(2)

    module = sys.argv[1]
    payload = _read_stdin()
    stdout, returncode = _run_module(module, payload)
    out = _claude_to_cursor(module, stdout, returncode)

    if module.endswith("pre_tool") and returncode != 0 and not out:
        out = {
            "continue": False,
            "permission": "deny",
            "user_message": "Willow pre_tool hook failed.",
            "agent_message": stdout.strip()[:500] or "Willow pre_tool hook failed.",
        }

    if out:
        print(json.dumps(out))
    sys.exit(0 if returncode == 0 else returncode)


if __name__ == "__main__":
    main()
