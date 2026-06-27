#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WILLOW_HOME_FALLBACK="${HOME}/github/.willow"

if [[ -z "${WILLOW_PYTHON:-}" ]]; then
    if [[ -x "${REPO_ROOT}/.venv-dev/bin/python3" ]]; then
        WILLOW_PYTHON="${REPO_ROOT}/.venv-dev/bin/python3"
    elif [[ -x "${HOME}/github/willow-2.0/.venv-dev/bin/python3" ]]; then
        WILLOW_PYTHON="${HOME}/github/willow-2.0/.venv-dev/bin/python3"
    elif [[ -n "${WILLOW_HOME:-}" && -x "${WILLOW_HOME}/venv/bin/python3" ]]; then
        WILLOW_PYTHON="${WILLOW_HOME}/venv/bin/python3"
    elif [[ -x "${WILLOW_HOME_FALLBACK}/venv/bin/python3" ]]; then
        WILLOW_PYTHON="${WILLOW_HOME_FALLBACK}/venv/bin/python3"
    elif [[ -x "${HOME}/.willow/venv/bin/python3" ]]; then
        WILLOW_PYTHON="${HOME}/.willow/venv/bin/python3"
    elif [[ -x "${HOME}/.willow-venv/bin/python3" ]]; then
        WILLOW_PYTHON="${HOME}/.willow-venv/bin/python3"
    else
        WILLOW_PYTHON="$(command -v python3)"
    fi
fi

if [[ -z "${WILLOW_HOME:-}" ]]; then
    WILLOW_HOME="$("${WILLOW_PYTHON}" -c "
import sys
from pathlib import Path
sys.path.insert(0, '${REPO_ROOT}')
from willow.fylgja.willow_home import fleet_home
print(fleet_home(Path('${REPO_ROOT}')))
" 2>/dev/null)" || WILLOW_HOME="${WILLOW_HOME_FALLBACK}"
fi

# Source the canonical fleet env (tracked in willow-config: $WILLOW_HOME/env).
# This is the single source of truth for persistent fleet-wide settings — paths,
# Postgres db, agent name, and policy flags such as
# WILLOW_COMPLETION_REQUIRE_EVIDENCE. The file is documented as
# "set -a && source ~/github/.willow/env && set +a"; honor that here so the MCP
# server actually picks it up instead of relying only on the launcher's
# .mcp.json env block. The active-agent file below still wins for
# WILLOW_AGENT_NAME, and secrets.sh (sourced next) still overrides any secret.
if [[ -f "${WILLOW_HOME}/env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${WILLOW_HOME}/env"
    set +a
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
ACTIVE_AGENT=""
if [[ -f "${ACTIVE_FILE}" ]]; then
    ACTIVE_AGENT="$(tr -d '[:space:]' < "${ACTIVE_FILE}")"
fi
if [[ -n "${ACTIVE_AGENT}" ]]; then
    WILLOW_AGENT_NAME="${ACTIVE_AGENT}"
elif [[ -z "${WILLOW_AGENT_NAME:-}" ]]; then
    WILLOW_AGENT_NAME="hanuman"
fi
export WILLOW_AGENT_NAME
export GROVE_SENDER="${WILLOW_AGENT_NAME}"
export GROVE_NAME="${WILLOW_AGENT_NAME}"
export WILLOW_PG_DB="${WILLOW_PG_DB:-willow_20}"
export WILLOW_PG_URL="${WILLOW_PG_URL:-postgresql://${USER:-$(id -un)}@localhost/${WILLOW_PG_DB}}"
export WILLOW_SAFE_ROOT="${WILLOW_SAFE_ROOT:-${HOME}/github/SAFE/Applications}"
export WILLOW_AGENTS_ROOT="${WILLOW_AGENTS_ROOT:-${HOME}/github/SAFE/Agents}"
export WILLOW_PGP_FINGERPRINT="${WILLOW_PGP_FINGERPRINT:-9B6F87BEB4AE56E23D3D055724AED1D0216053F5}"
export MAI_SECURITY_CONFIG="${MAI_SECURITY_CONFIG:-${HOME}/.markdownai/security.json}"
# Tool picker size: minimal | core | standard (default) | full
export WILLOW_MCP_PROFILE="${WILLOW_MCP_PROFILE:-standard}"

cd "${REPO_ROOT}"
exec "${WILLOW_PYTHON}" -m sap.unified_mcp "$@"
