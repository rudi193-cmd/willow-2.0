#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source local secrets (not tracked). Create ~/.willow/secrets.sh with:
#   export ANTHROPIC_API_KEY="sk-ant-..."
if [[ -f "${HOME}/.willow/secrets.sh" ]]; then
    # shellcheck disable=SC1091
    source "${HOME}/.willow/secrets.sh"
fi
GROVE_ROOT="${WILLOW_GROVE_ROOT:-${HOME}/github/safe-app-willow-grove}"

export PYTHONPATH="${REPO_ROOT}:${GROVE_ROOT}"
export WILLOW_ROOT="${REPO_ROOT}"
export WILLOW_AGENT_NAME="${WILLOW_AGENT_NAME:-agent}"
export WILLOW_PG_DB="${WILLOW_PG_DB:-willow_20}"
export WILLOW_PG_URL="${WILLOW_PG_URL:-postgresql://${USER:-$(id -un)}@localhost/${WILLOW_PG_DB}}"
export MAI_SECURITY_CONFIG="${MAI_SECURITY_CONFIG:-${HOME}/.markdownai/security.json}"

cd "${REPO_ROOT}"
exec "${REPO_ROOT}/.venv-dev/bin/python3" -m sap.unified_mcp "$@"
