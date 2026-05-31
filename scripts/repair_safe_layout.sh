#!/usr/bin/env bash
# Move ~/SAFE → ~/github/SAFE (if needed), wire symlink, audit paths.
# Run in a host terminal after re-signing manifests.
set -euo pipefail

HOME_DIR="${HOME}"
GITHUB="${HOME_DIR}/github"
CANON="${GITHUB}/SAFE"
LINK="${HOME_DIR}/SAFE"
REPO="${GITHUB}/willow-2.0"

run() { echo "+ $*"; "$@"; }

echo "==> SAFE layout"
if [[ -L "${LINK}" ]] && [[ "$(readlink -f "${LINK}")" == "$(readlink -f "${CANON}")" ]]; then
  echo "OK: ~/SAFE -> ~/github/SAFE"
elif [[ -d "${LINK}" && ! -L "${LINK}" ]]; then
  if [[ -e "${CANON}" ]]; then
    echo "ERROR: real ~/SAFE and ~/github/SAFE both exist — merge manually" >&2
    exit 1
  fi
  run mkdir -p "${GITHUB}"
  run mv "${LINK}" "${CANON}"
  run ln -sfn "${CANON}" "${LINK}"
  echo "Moved ~/SAFE → ~/github/SAFE and linked back"
elif [[ ! -e "${LINK}" && ! -e "${CANON}" ]]; then
  run mkdir -p "${CANON}/Applications" "${CANON}/Agents"
  run ln -sfn "${CANON}" "${LINK}"
  echo "Created empty ~/github/SAFE skeleton"
else
  run ln -sfn "${CANON}" "${LINK}"
fi

echo ""
echo "==> Path audit"
if [[ -x "${REPO}/scripts/audit_safe_paths.py" ]]; then
  PYTHONPATH="${REPO}" python3 "${REPO}/scripts/audit_safe_paths.py" || true
else
  readlink -f "${LINK}" "${CANON}/Applications" "${CANON}/Agents" 2>/dev/null || true
fi

echo ""
echo "==> After re-sign, verify"
cat <<'EOF'
  export WILLOW_SAFE_ROOT=~/github/SAFE/Applications
  export WILLOW_AGENTS_ROOT=~/github/SAFE/Agents
  cd ~/github/willow-2.0
  python3 scripts/sync_safe_agent_manifests.py --force   # fleet agents
  ./willow.sh verify
  ./willow agents install <your-agent> --ide all         # refresh IDE MCP env
EOF
