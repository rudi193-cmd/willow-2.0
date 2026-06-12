#!/usr/bin/env bash
# audit_canonical_home.sh — Symlink + identity checks for canonical fleet home layout.
#
# Usage:
#   bash scripts/audit_canonical_home.sh
#
# Exit 0 when checks pass; non-zero on hard failures.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

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

WILLOW_HOME="${WILLOW_HOME:-${HOME}/github/.willow}"
export WILLOW_ROOT="${ROOT}"
export WILLOW_HOME
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"

fail=0
warn=0

_ok() { echo "  OK: $1"; }
_warn() { echo "  WARN: $1"; warn=$((warn + 1)); }
_fail() { echo "  FAIL: $1"; fail=$((fail + 1)); }

echo "=== canonical home ==="
echo "WILLOW_HOME=${WILLOW_HOME}"

if [[ -d "${WILLOW_HOME}" ]]; then
  _ok "WILLOW_HOME exists"
else
  _fail "WILLOW_HOME missing (${WILLOW_HOME})"
fi

if [[ -L "${HOME}/.willow" ]]; then
  alias_target="$(readlink -f "${HOME}/.willow")"
  home_target="$(readlink -f "${WILLOW_HOME}" 2>/dev/null || echo "${WILLOW_HOME}")"
  if [[ "${alias_target}" == "${home_target}" ]]; then
    _ok "~/.willow alias → ${alias_target}"
  else
    _warn "~/.willow (${alias_target}) != WILLOW_HOME (${home_target})"
  fi
elif [[ -d "${HOME}/.willow" ]]; then
  _warn "~/.willow is a directory, not a symlink"
else
  _warn "~/.willow missing (alias optional)"
fi

echo ""
echo "=== repo contract ==="
if [[ -f "willow.md" && ! -L "willow.md" ]]; then
  _ok "willow.md is a tracked public file (not symlinked)"
elif [[ -L "willow.md" ]]; then
  _warn "willow.md should be a real public file in git, not a symlink"
else
  _fail "willow.md missing — public contract required at repo root"
fi

echo ""
echo "=== fleet-home symlinks ==="
for pair in \
  "willow/fylgja/config/fleet.env:${WILLOW_HOME}/env" \
  "willow/fylgja/config/settings.global.json:${WILLOW_HOME}/settings.global.json"; do
  link="${pair%%:*}"
  target="${pair#*:}"
  if [[ -L "${link}" ]]; then
    resolved="$(readlink -f "${link}")"
    if [[ -f "${target}" && "${resolved}" == "$(readlink -f "${target}")" ]]; then
      _ok "${link} → ${target}"
    else
      _warn "${link} symlink target mismatch (→ ${resolved})"
    fi
  elif [[ -f "${link}" ]]; then
    _warn "${link} is a regular file, not symlinked to fleet home"
  else
    _warn "${link} missing — run: python3 -m willow.fylgja.link_fleet_home"
  fi
done

echo ""
echo "=== active agent + MCP export ==="
if [[ -f ".willow/active-agent" ]]; then
  active="$(tr -d '[:space:]' < .willow/active-agent)"
  _ok "active-agent=${active}"
  if [[ -f "agents/${active}/config/mcp.json" ]]; then
    _ok "agents/${active}/config/mcp.json present"
  else
    _fail "missing agents/${active}/config/mcp.json"
  fi
  home_mcp="${WILLOW_HOME}/mcp/willow-2.0.mcp.json"
  if [[ -f "${home_mcp}" ]]; then
    _ok "fleet home MCP export present"
  else
    _warn "missing ${home_mcp} — run install_project"
  fi
else
  _fail ".willow/active-agent missing"
fi

echo ""
echo "=== identity matrix ==="
"${PYTHON}" - <<'PY' || fail=$((fail + 1))
import json
import os
import sys

os.chdir(os.environ["WILLOW_ROOT"])
from willow.fylgja.identity_bind import collect_identity_matrix

m = collect_identity_matrix()
print(json.dumps({"coherent": m.get("coherent"), "drift": m.get("drift")}, indent=2))
if not m.get("coherent"):
    sys.exit(1)
PY

echo ""
echo "audit_canonical_home: failures=${fail} warnings=${warn}"
[[ "${fail}" -eq 0 ]]
