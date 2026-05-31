#!/usr/bin/env bash
# Report-only mypy — matches CI lint job; does not block commit/push.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MYPY="${MYPY:-mypy}"
if ! command -v "$MYPY" &>/dev/null; then
  for candidate in "${ROOT}/.venv-dev/bin/mypy" "${ROOT}/.venv/bin/mypy"; do
    if [[ -x "$candidate" ]]; then
      MYPY="$candidate"
      break
    fi
  done
fi

if ! command -v "$MYPY" &>/dev/null && [[ ! -x "$MYPY" ]]; then
  echo "mypy not installed — skip"
  exit 0
fi

echo "==> mypy core sap willow (report-only)"
"$MYPY" core sap willow || true
