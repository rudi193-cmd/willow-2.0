#!/usr/bin/env bash
# check_context.sh — Willow Context Sentinel
# Part of the willow-context-sentinel OpenClaw skill.
#
# Reads anchor_state_{agent}.json (canonical; mirrored from SOIL by hooks),
# then outputs one of:
#   STATUS_OK      — prompt_count < 15, postgres up
#   COMPACT_NOW    — prompt_count 15–25
#   HANDOFF_NOW    — prompt_count > 25
#   POSTGRES_DOWN  — postgres reported as down in session_anchor.json
#
# Exits 0 in all cases. Missing state files are treated as STATUS_OK
# (fail open) with a warning on stderr.

set -euo pipefail

WILLOW_HOME="${WILLOW_HOME:-${HOME}/github/.willow}"
REPO_ROOT="${WILLOW_ROOT:-${HOME}/github/willow-2.0}"
ACTIVE_AGENT_FILE="${REPO_ROOT}/.willow/active-agent"
ACTIVE_AGENT=""
if [[ -f "$ACTIVE_AGENT_FILE" ]]; then
  ACTIVE_AGENT="$(tr -d '[:space:]' < "$ACTIVE_AGENT_FILE")"
fi
if [[ -n "$ACTIVE_AGENT" ]]; then
  AGENT="$ACTIVE_AGENT"
elif [[ -n "${WILLOW_AGENT_NAME:-}" ]]; then
  AGENT="${WILLOW_AGENT_NAME}"
else
  AGENT="hanuman"
fi
SESSION_ANCHOR="$(
  export WILLOW_AGENT_NAME="$AGENT"
  export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"
  python3 -c "
from pathlib import Path
import os
from willow.fylgja.handoff_project import resolve_handoff_project, session_anchor_path
from willow.fylgja.project_env import workspace_root
agent = os.environ['WILLOW_AGENT_NAME']
ws = workspace_root() or Path.cwd()
project = resolve_handoff_project(workspace=ws)
print(session_anchor_path(agent, project))
" 2>/dev/null || echo "${WILLOW_HOME}/session_anchor_${AGENT}.json"
)"

# ---------------------------------------------------------------------------
# Postgres check — takes priority over all context checks
# ---------------------------------------------------------------------------
if [[ -f "$SESSION_ANCHOR" ]]; then
    pg_status=$(python3 -c "
import json, sys
try:
    data = json.load(open('$SESSION_ANCHOR'))
    val = str(data.get('postgres', '')).lower()
    print(val)
except Exception:
    print('')
" 2>/dev/null || true)

    if [[ "$pg_status" == "down" || "$pg_status" == "false" ]]; then
        echo "POSTGRES_DOWN"
        exit 0
    fi
else
    echo "WARNING: $SESSION_ANCHOR not found — skipping postgres check" >&2
fi

# ---------------------------------------------------------------------------
# Context check via shared anchor_state module
# ---------------------------------------------------------------------------
export WILLOW_AGENT_NAME="$AGENT"
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"
context_status=$(python3 -c "
import os
from willow.fylgja.anchor_state import context_status, prompt_count
agent = '$AGENT'
sid = os.environ.get('WILLOW_SESSION_ID') or None
count = prompt_count(agent, sid)
print(context_status(count))
" 2>/dev/null) || {
    echo "WARNING: anchor_state read failed — defaulting to STATUS_OK" >&2
    echo "STATUS_OK"
    exit 0
}

echo "$context_status"
