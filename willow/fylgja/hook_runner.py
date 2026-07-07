#!/usr/bin/env python3
"""
hook_runner.py — Unified Fylgja hook runner for Cursor and Claude Code.

Usage:
  python3 -m willow.fylgja.hook_runner --format cursor willow.fylgja.events.session_start
  python3 -m willow.fylgja.hook_runner --format claude willow.fylgja.events.pre_tool
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from willow.fylgja.project_env import event_module, hook_python, merge_hook_env, repo_root


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
        sid = payload.get("conversation_id") or payload.get("parent_conversation_id", "")

        if event == "subagentStart":
            return {
                "session_id": sid,
                "tool_name": "Task",
                "tool_input": {
                    "subagent_type": payload.get("subagent_type", ""),
                    "description": payload.get("task", ""),
                },
            }

        # beforeMCPExecution payloads also carry tool_name — must run before the
        # generic preToolUse branch or boot_gate sees "fleet_status" not mcp__* .
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
                "session_id": sid,
                "tool_name": f"mcp__{server}__{tool}",
                "tool_input": tool_input,
            }

        if event == "preToolUse" or payload.get("tool_name"):
            tool = payload.get("tool_name", "")
            tool_map = {
                "Shell": "Bash",
                "Grep": "Grep",
                "Write": "Write",
                "Read": "Read",
                "Task": "Task",
                "Edit": "Edit",
                "StrReplace": "Edit",
            }
            mapped = tool_map.get(tool, tool)
            tool_input = payload.get("tool_input") or {}
            if not isinstance(tool_input, dict):
                tool_input = {}
            if mapped == "Bash" and "command" not in tool_input:
                cmd = tool_input.get("command") or payload.get("command", "")
                tool_input = {"command": cmd}
            # Cursor sends "path" where Claude-format events use "file_path".
            # Without this, pre_tool guards (boot gate, hook tamper) can't see
            # which file a Cursor Read/Write/Edit touches — the boot sentinel
            # Write was invisible, forcing operators to seed it by hand.
            if mapped in ("Read", "Write", "Edit") and "file_path" not in tool_input:
                path = tool_input.get("path") or payload.get("path", "")
                if path:
                    tool_input = {**tool_input, "file_path": path}
            return {
                "session_id": sid,
                "tool_name": mapped,
                "tool_input": tool_input,
            }

        command = payload.get("command", "")
        return {
            "session_id": sid,
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


def run_module(fmt: str, module: str, payload: dict | None = None) -> tuple[str, int]:
    root = repo_root()
    merged = merge_hook_env(root)
    py = hook_python(root)
    full_module = event_module(module)

    stdin_payload = payload
    if fmt == "cursor":
        stdin_payload = _cursor_to_claude(full_module, payload or {})

    proc = subprocess.run(
        [str(py), "-m", full_module],
        input=json.dumps(stdin_payload or {}),
        capture_output=True,
        text=True,
        env=merged,
        cwd=str(root),
    )
    stdout = proc.stdout or ""
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return stdout, proc.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified Fylgja hook runner")
    parser.add_argument("--format", choices=("cursor", "claude"), required=True)
    parser.add_argument("module", help="willow.fylgja.events.* module or short name")
    args = parser.parse_args()

    payload = _read_stdin() if not sys.stdin.isatty() else {}
    full_module = event_module(args.module)
    stdout, returncode = run_module(args.format, full_module, payload)

    if args.format == "claude":
        if stdout:
            sys.stdout.write(stdout)
            if not stdout.endswith("\n"):
                sys.stdout.write("\n")
        raise SystemExit(returncode)

    out = _claude_to_cursor(full_module, stdout, returncode)
    if full_module.endswith("pre_tool") and returncode != 0 and not out:
        out = {
            "continue": False,
            "permission": "deny",
            "user_message": "Willow pre_tool hook failed.",
            "agent_message": stdout.strip()[:500] or "Willow pre_tool hook failed.",
        }
    if out:
        print(json.dumps(out))
    raise SystemExit(0 if returncode == 0 else returncode)


if __name__ == "__main__":
    main()
