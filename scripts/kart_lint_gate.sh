#!/usr/bin/env bash
# kart_lint_gate.sh — Run before git commit/push in Kart scripts (same scope as CI lint).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "${ROOT}/scripts/lint_first_party.sh"
