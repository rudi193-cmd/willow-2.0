#!/usr/bin/env bash
# Remove non-Willow editable installs from .venv-dev (SAFE app dev cruft).
# Keeps: willow (editable). MCP apps run via separate PYTHONPATH / app_install.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/.venv-dev"
PIP="${VENV}/bin/pip"
PY="${VENV}/bin/python3"
[[ -x "${PIP}" ]] || { echo "Missing ${VENV}" >&2; exit 1; }

EXTRA=(
  courtlistener-mcp
  safe-app-ask-jeles
  safe-app-semantic-translator
  safe-app-source-trail
)

echo "Before:"
"${PIP}" list | grep -E '^(willow|courtlistener|safe-app)' || true

for pkg in "${EXTRA[@]}"; do
  if "${PIP}" show "${pkg}" >/dev/null 2>&1; then
    echo "Uninstalling ${pkg}…"
    "${PIP}" uninstall -y "${pkg}"
  else
    echo "Skip ${pkg} (not installed)"
  fi
done

echo ""
echo "After:"
"${PIP}" list | grep -E '^(willow|courtlistener|safe-app)' || echo "(only willow should remain)"

echo ""
echo "Smoke import:"
"${PY}" -c "import mcp, sap, willow.fylgja, core.source_trail; print('imports OK')"

echo ""
"${PIP}" check
