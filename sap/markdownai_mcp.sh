#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NODE_BIN="${MARKDOWNAI_NODE_BIN:-}"
if [[ -z "${NODE_BIN}" ]]; then
  NODE_BIN="$(command -v node || true)"
fi
if [[ -z "${NODE_BIN}" ]]; then
  for candidate in "${HOME}"/.local/share/fnm/node-versions/*/installation/bin/node; do
    if [[ -x "${candidate}" ]]; then
      NODE_BIN="${candidate}"
      break
    fi
  done
fi
if [[ -z "${NODE_BIN}" ]]; then
  echo "markdownai_mcp.sh: node not found" >&2
  exit 1
fi

MARKDOWNAI_DIST_DIR="${MARKDOWNAI_DIST_DIR:-}"
if [[ -z "${MARKDOWNAI_DIST_DIR}" ]]; then
  INSTALL_ROOT="$(cd "$(dirname "${NODE_BIN}")/.." && pwd)"
  CANDIDATE_DIST="${INSTALL_ROOT}/lib/node_modules/@markdownai/mcp/dist"
  if [[ -d "${CANDIDATE_DIST}" ]]; then
    MARKDOWNAI_DIST_DIR="${CANDIDATE_DIST}"
  fi
fi
if [[ -z "${MARKDOWNAI_DIST_DIR}" ]]; then
  echo "markdownai_mcp.sh: MARKDOWNAI_DIST_DIR not found" >&2
  exit 1
fi

export WILLOW_PG_URL="${WILLOW_PG_URL:-postgresql://${USER:-$(id -un)}@localhost/willow_20}"
export MAI_SECURITY_CONFIG="${MAI_SECURITY_CONFIG:-${HOME}/.markdownai/security.json}"
export MARKDOWNAI_DIST_DIR

exec "${NODE_BIN}" "${REPO_ROOT}/sap/markdownai_server.mjs" "$@"
