#!/usr/bin/env bash
# LoCoMo benchmark runner — Haiku QA, memory v2.
# Usage:
#   ./run_locomo.sh          # conv-0 smoke
#   ./run_locomo.sh --all    # full LoCoMo-10
set -e

WILLOW_ROOT="${WILLOW_ROOT:-/home/sean-campbell/github/willow-2.0}"
VENV_PY="${VENV_PY:-$WILLOW_ROOT/.venv-dev/bin/python3}"
CLAUDE_MODEL="${CLAUDE_MODEL:-claude-haiku-4-5-20251001}"

if [[ -z "$ANTHROPIC_API_KEY" ]]; then
  ANTHROPIC_API_KEY="$("$VENV_PY" -c "
import sys
sys.path.insert(0, '$WILLOW_ROOT')
from sap.core.inference import load_credential
print(load_credential('ANTHROPIC_API_KEY') or '')
")"
  export ANTHROPIC_API_KEY
fi

if [[ -z "$ANTHROPIC_API_KEY" ]]; then
  echo "ERROR: ANTHROPIC_API_KEY not set and not in ~/.willow/secrets."
  echo "  Store once: cd ~/github/willow-2.0 && ./willow.sh providers enable anthropic --key sk-ant-..."
  exit 1
fi

cd "$(dirname "$0")"

ARGS=(--mode qa --llm claude --claude-model "$CLAUDE_MODEL" --semantic --top-k 10 --memory-profile v2)

if [[ "${1:-}" == "--all" ]]; then
    echo "Key present (len=${#ANTHROPIC_API_KEY}). Starting LoCoMo-10 (Haiku, memory v2)..."
    ARGS=(--all --force-ingest "${ARGS[@]}")
    shift || true
else
    echo "Key present (len=${#ANTHROPIC_API_KEY}). Starting conv-0 smoke (Haiku, memory v2)..."
    ARGS=(--conv-index 0 --force-ingest "${ARGS[@]}")
fi

PYTHONPATH="$(pwd):$WILLOW_ROOT" \
    "$VENV_PY" path_a_locomo_pilot.py "${ARGS[@]}" "$@"
