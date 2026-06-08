#!/usr/bin/env bash
# comfort_check.sh — Repeatable comfort gate (CI-safe or full local).
#
# Usage:
#   ./scripts/comfort_check.sh           # CI-safe (default)
#   ./scripts/comfort_check.sh --local   # + symlinks, systemd, agents check, verify
#   ./scripts/comfort_check.sh --ci      # explicit CI mode (same as default)
#
# Exit 0 only if all required checks pass.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

MODE="ci"
[[ "${1:-}" == "--local" ]] && MODE="local"
[[ "${1:-}" == "--ci" ]] && MODE="ci"

PYTHON="${WILLOW_PYTHON:-}"
if [[ -z "${PYTHON}" ]]; then
  if [[ -x "${ROOT}/.venv-dev/bin/python3" ]]; then
    PYTHON="${ROOT}/.venv-dev/bin/python3"
  elif [[ -x "${HOME}/github/willow-2.0/.venv-dev/bin/python3" ]]; then
    PYTHON="${HOME}/github/willow-2.0/.venv-dev/bin/python3"
  elif [[ -x "${WILLOW_HOME:-${HOME}/github/.willow}/venv/bin/python3" ]]; then
    PYTHON="${WILLOW_HOME:-${HOME}/github/.willow}/venv/bin/python3"
  elif [[ -x "${HOME}/.willow/venv/bin/python3" ]]; then
    PYTHON="${HOME}/.willow/venv/bin/python3"
  elif [[ -x "${HOME}/.willow-venv/bin/python3" ]]; then
    PYTHON="${HOME}/.willow-venv/bin/python3"
  else
    PYTHON="$(command -v python3)"
  fi
fi

export WILLOW_ROOT="${WILLOW_ROOT:-${ROOT}}"
export WILLOW_MCP_PROFILE="${WILLOW_MCP_PROFILE:-full}"
export PYTHONPATH="${WILLOW_ROOT}:${PYTHONPATH:-}"

total_fail=0
total_warn=0

_run() {
  local name="$1"
  shift
  echo ""
  echo "=== ${name} ==="
  if "$@"; then
    echo "=== ${name}: PASS ==="
  else
    echo "=== ${name}: FAIL ==="
    total_fail=$((total_fail + 1))
  fi
}

_path_guard() {
  bash scripts/path_guard.sh
}

_mcp_registry() {
  "${PYTHON}" scripts/check_mcp_registry.py --strict
}

_layout() {
  bash scripts/verify_layout.sh
}

_fast_tests() {
  "${PYTHON}" -m pytest tests/test_mcp_profiles.py tests/test_mai_tools.py -q --timeout=30
}

_bifrost_db_warn() {
  if ! command -v rg >/dev/null 2>&1; then
    echo "rg not installed — skip bifrost scan"
    return 0
  fi
  local missing
  missing="$(rg -l '@db' willow/fylgja/skills willow/fylgja/powers 2>/dev/null \
    | rg -v '@fallback|fallback' 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "${missing}" -gt 0 ]]; then
    echo "WARN: ~${missing} Bifrost paths mention @db without fallback in same file"
    total_warn=$((total_warn + missing))
  else
    echo "Bifrost @db fallback scan OK"
  fi
  return 0
}

_ci_stubs() {
  mkdir -p "${WILLOW_HOME:-${ROOT}/.ci-willow}/store" 2>/dev/null || true
  if [[ "${MODE}" == "ci" ]]; then
    export WILLOW_HOME="${WILLOW_HOME:-${ROOT}/.ci-willow}"
    export WILLOW_SAFE_ROOT="${WILLOW_SAFE_ROOT:-${ROOT}/.ci-safe/Applications}"
    export WILLOW_AGENTS_ROOT="${WILLOW_AGENTS_ROOT:-${ROOT}/.ci-safe/Agents}"
    mkdir -p "${WILLOW_SAFE_ROOT}" "${WILLOW_AGENTS_ROOT}"
    mkdir -p .willow
    echo "willow" > .willow/active-agent
    if [[ -f agents/willow/config/mcp.json.example ]]; then
      sed -e "s|{{REPO_ROOT}}|${ROOT}|g" -e "s|{{HOME}}|${HOME}|g" \
        agents/willow/config/mcp.json.example > agents/willow/config/mcp.json
    fi
    if [[ ! -e .cursor/hooks.json && -f willow/fylgja/config/cursor-hooks.json ]]; then
      mkdir -p .cursor
      ln -sf ../willow/fylgja/config/cursor-hooks.json .cursor/hooks.json
    fi
  fi
}

_agents_rails_ci() {
  _ci_stubs
  local issues=0
  local active
  active="$(tr -d '[:space:]' < .willow/active-agent)"
  [[ -f "agents/${active}/config/mcp.json" ]] || { echo "missing agents/${active}/config/mcp.json"; issues=1; }
  [[ -f willow/fylgja/bin/fylgja-hook ]] || { echo "missing fylgja-hook"; issues=1; }
  [[ -f willow/fylgja/config/kart-sandbox.json ]] || { echo "missing kart-sandbox.json"; issues=1; }
  [[ -e .cursor/hooks.json ]] || { echo "missing .cursor/hooks.json"; issues=1; }
  [[ "${issues}" -eq 0 ]]
}

_agents_check() {
  _ci_stubs
  export WILLOW_AGENT_NAME="${WILLOW_AGENT_NAME:-willow}"
  cd "${ROOT}"
  "${PYTHON}" -m willow.fylgja.agents_cli check
}

_local_symlinks() {
  set +e
  local ok=1
  for link in "${HOME}/.willow" "${HOME}/willow-2.0" "${HOME}/SAFE"; do
    if [[ -L "${link}" ]]; then
      echo "  OK: ${link} -> $(readlink -f "${link}")"
    else
      echo "  WARN: ${link} is not a symlink"
      ok=0
    fi
  done
  set -e
  [[ "${ok}" -eq 1 ]]
}

_local_systemd() {
  local units=(drop-server nest-watcher kart-worker grove-mcp willow-grove-listen)
  local bad=0
  for u in "${units[@]}"; do
    if systemctl --user is-active --quiet "${u}.service" 2>/dev/null; then
      echo "  OK: ${u}.service active"
    else
      echo "  WARN: ${u}.service not active"
      bad=$((bad + 1))
    fi
  done
  [[ "${bad}" -eq 0 ]]
}

_local_verify() {
  bash "${ROOT}/willow.sh" verify
}

_retrieval_gold() {
  "${PYTHON}" scripts/retrieval_gold_check.py
}

echo "[comfort_check] mode=${MODE} root=${ROOT}"

if [[ "${MODE}" == "ci" ]]; then
  _ci_stubs
fi

_run "path-guard" _path_guard
_run "mcp-registry-strict" _mcp_registry
_run "verify-layout" _layout
_run "fast-mcp-tests" _fast_tests
_run "bifrost-db-scan" _bifrost_db_warn

if [[ "${MODE}" == "local" ]]; then
  _run "home-symlinks" _local_symlinks
  _run "systemd-units" _local_systemd || true
  _run "agents-check" _agents_check
  _run "retrieval-gold" _retrieval_gold
  _run "safe-verify" _local_verify
else
  _run "agents-rails-ci" _agents_rails_ci
fi

echo ""
echo "[comfort_check] required_failures=${total_fail} warnings=${total_warn}"
if [[ "${total_fail}" -gt 0 ]]; then
  exit 1
fi
echo "[comfort_check] OK"
