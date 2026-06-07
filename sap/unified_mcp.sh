#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

WILLOW_HOME="${WILLOW_HOME:-${HOME}/github/.willow}"

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
ACTIVE_FILE="${REPO_ROOT}/.willow/active-agent"
if [[ -z "${WILLOW_AGENT_NAME:-}" && -f "${ACTIVE_FILE}" ]]; then
    WILLOW_AGENT_NAME="$(tr -d '[:space:]' < "${ACTIVE_FILE}")"
fi
export WILLOW_AGENT_NAME="${WILLOW_AGENT_NAME:-hanuman}"
export GROVE_SENDER="${GROVE_SENDER:-${WILLOW_AGENT_NAME}}"
export GROVE_NAME="${GROVE_NAME:-${WILLOW_AGENT_NAME}}"
export WILLOW_PG_DB="${WILLOW_PG_DB:-willow_20}"
export WILLOW_PG_URL="${WILLOW_PG_URL:-postgresql://${USER:-$(id -un)}@localhost/${WILLOW_PG_DB}}"
export MAI_SECURITY_CONFIG="${MAI_SECURITY_CONFIG:-${HOME}/.markdownai/security.json}"
# Tool picker size: minimal | core | standard (default) | full
export WILLOW_MCP_PROFILE="${WILLOW_MCP_PROFILE:-standard}"

cd "${REPO_ROOT}"
exec "${REPO_ROOT}/.venv-dev/bin/python3" -m sap.unified_mcp "$@"
