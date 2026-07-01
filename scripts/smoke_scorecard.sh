#!/usr/bin/env bash
# SLI scorecard smoke tier — pytest + fleet retrieval gold.
# Uses .venv-dev when present (see CONTRIBUTING.md); bare `pytest` is not on PATH.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -x "${ROOT}/.venv-dev/bin/python" ]]; then
  PY="${ROOT}/.venv-dev/bin/python"
elif [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  PY="${VIRTUAL_ENV}/bin/python"
else
  PY="python3"
fi

export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

echo "smoke_scorecard: python=${PY}"
"${PY}" -m pytest --ignore=tests/adversarial/e2e -q
"${PY}" scripts/retrieval_gold_check.py
