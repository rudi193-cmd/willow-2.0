#!/usr/bin/env bash
# Bandit SAST on first-party Python — matches CI security job (report-only).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BANDIT="${BANDIT:-bandit}"
if ! command -v "$BANDIT" &>/dev/null; then
  for candidate in "${ROOT}/.venv-dev/bin/bandit" "${ROOT}/.venv/bin/bandit"; do
    if [[ -x "$candidate" ]]; then
      BANDIT="$candidate"
      break
    fi
  done
fi

if ! command -v "$BANDIT" &>/dev/null && [[ ! -x "$BANDIT" ]]; then
  echo "bandit not installed — skip"
  exit 0
fi

echo "==> bandit -r core sap willow (report-only, medium+ severity)"
"$BANDIT" -r core sap willow -ll -f txt || true
