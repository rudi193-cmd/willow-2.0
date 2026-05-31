#!/usr/bin/env bash
# First-party lint scope — matches CI lint job (Phase 1).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUFF="${RUFF:-ruff}"
if ! command -v "$RUFF" &>/dev/null; then
  for candidate in "${ROOT}/.venv-dev/bin/ruff" "${ROOT}/.venv/bin/ruff"; do
    if [[ -x "$candidate" ]]; then
      RUFF="$candidate"
      break
    fi
  done
fi

echo "==> ruff check core sap willow tests scripts"
"$RUFF" check core sap willow tests scripts

if command -v mypy &>/dev/null || [[ -x "${ROOT}/.venv-dev/bin/mypy" ]]; then
  MYPY="${MYPY:-mypy}"
  if ! command -v "$MYPY" &>/dev/null; then
    MYPY="${ROOT}/.venv-dev/bin/mypy"
  fi
  echo "==> mypy (report-only — does not fail this script)"
  "$MYPY" core sap willow || true
fi
