#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

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

# Source local secrets (not tracked). Create $WILLOW_HOME/secrets.sh with:
#   export ANTHROPIC_API_KEY="sk-ant-..."
if [[ -f "${WILLOW_HOME}/secrets.sh" ]]; then
    # shellcheck disable=SC1091
    source "${WILLOW_HOME}/secrets.sh"
elif [[ -f "${HOME}/.willow/secrets.sh" ]]; then
    # shellcheck disable=SC1091
    source "${HOME}/.willow/secrets.sh"
fi
GROVE_ROOT="${WILLOW_GROVE_ROOT:-${HOME}/github/safe-app-willow-grove}"

export PYTHONPATH="${REPO_ROOT}:${GROVE_ROOT}"
export WILLOW_ROOT="${REPO_ROOT}"
export WILLOW_HOME="${WILLOW_HOME}"
export WILLOW_PYTHON
ACTIVE_FILE="${REPO_ROOT}/.willow/active-agent"
if [[ -z "${WILLOW_AGENT_NAME:-}" && -f "${ACTIVE_FILE}" ]]; then
    WILLOW_AGENT_NAME="$(tr -d '[:space:]' < "${ACTIVE_FILE}")"
fi
export WILLOW_AGENT_NAME="${WILLOW_AGENT_NAME:-hanuman}"
export GROVE_SENDER="${WILLOW_AGENT_NAME}"
export GROVE_NAME="${WILLOW_AGENT_NAME}"
export WILLOW_PG_DB="${WILLOW_PG_DB:-willow_20}"
export WILLOW_PG_URL="${WILLOW_PG_URL:-postgresql://${USER:-$(id -un)}@localhost/${WILLOW_PG_DB}}"
export MAI_SECURITY_CONFIG="${MAI_SECURITY_CONFIG:-${HOME}/.markdownai/security.json}"
# Tool picker size: minimal | core (default) | standard | full
export WILLOW_MCP_PROFILE="${WILLOW_MCP_PROFILE:-core}"

cd "${REPO_ROOT}"
exec "${WILLOW_PYTHON}" -m sap.unified_mcp "$@"
