#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
GROVE_ROOT="${WILLOW_GROVE_ROOT:-${HOME}/github/safe-app-willow-grove}"

export PYTHONPATH="${REPO_ROOT}:${GROVE_ROOT}"
export WILLOW_ROOT="${REPO_ROOT}"
export WILLOW_HOME="${WILLOW_HOME:-${HOME}/github/.willow}"
export WILLOW_AGENT_NAME="${WILLOW_AGENT_NAME:-agent}"
export WILLOW_SAFE_ROOT="${WILLOW_SAFE_ROOT:-${HOME}/SAFE/Applications}"
export WILLOW_STORE_ROOT="${WILLOW_STORE_ROOT:-${WILLOW_HOME}/store}"
export WILLOW_VAULT="${WILLOW_VAULT:-${WILLOW_HOME}/vault.db}"
export WILLOW_PG_DB="${WILLOW_PG_DB:-willow_20}"
export WILLOW_PGP_FINGERPRINT="${WILLOW_PGP_FINGERPRINT:-9B6F87BEB4AE56E23D3D055724AED1D0216053F5}"

exec "${REPO_ROOT}/.venv-dev/bin/python3" "${REPO_ROOT}/sap/sap_mcp.py" "$@"
