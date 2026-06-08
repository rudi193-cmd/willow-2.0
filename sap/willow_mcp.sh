#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
GROVE_ROOT="${WILLOW_GROVE_ROOT:-${HOME}/github/safe-app-willow-grove}"
WILLOW_HOME="${WILLOW_HOME:-${HOME}/github/.willow}"

if [[ -z "${WILLOW_PYTHON:-}" ]]; then
    if [[ -x "${REPO_ROOT}/.venv-dev/bin/python3" ]]; then
        WILLOW_PYTHON="${REPO_ROOT}/.venv-dev/bin/python3"
    elif [[ -x "${HOME}/github/willow-2.0/.venv-dev/bin/python3" ]]; then
        WILLOW_PYTHON="${HOME}/github/willow-2.0/.venv-dev/bin/python3"
    elif [[ -x "${WILLOW_HOME}/venv/bin/python3" ]]; then
        WILLOW_PYTHON="${WILLOW_HOME}/venv/bin/python3"
    elif [[ -x "${HOME}/.willow/venv/bin/python3" ]]; then
        WILLOW_PYTHON="${HOME}/.willow/venv/bin/python3"
    elif [[ -x "${HOME}/.willow-venv/bin/python3" ]]; then
        WILLOW_PYTHON="${HOME}/.willow-venv/bin/python3"
    else
        WILLOW_PYTHON="$(command -v python3)"
    fi
fi

export PYTHONPATH="${REPO_ROOT}:${GROVE_ROOT}"
export WILLOW_ROOT="${REPO_ROOT}"
export WILLOW_HOME
export WILLOW_PYTHON
export WILLOW_AGENT_NAME="${WILLOW_AGENT_NAME:-agent}"
export WILLOW_SAFE_ROOT="${WILLOW_SAFE_ROOT:-${HOME}/SAFE/Applications}"
export WILLOW_STORE_ROOT="${WILLOW_STORE_ROOT:-${WILLOW_HOME}/store}"
export WILLOW_VAULT="${WILLOW_VAULT:-${WILLOW_HOME}/vault.db}"
export WILLOW_PG_DB="${WILLOW_PG_DB:-willow_20}"
export WILLOW_PGP_FINGERPRINT="${WILLOW_PGP_FINGERPRINT:-9B6F87BEB4AE56E23D3D055724AED1D0216053F5}"

exec "${WILLOW_PYTHON}" "${REPO_ROOT}/sap/sap_mcp.py" "$@"
