#!/usr/bin/env bash
# Refresh editable willow metadata after pyproject.toml dependency changes.
# PEP 660 editable installs keep metadata in site-packages, not willow.egg-info/.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/.venv-dev"
PIP="${VENV}/bin/pip"
[[ -x "${PIP}" ]] || { echo "Missing ${VENV} — run bash setup.sh first" >&2; exit 1; }

rm -rf "${ROOT}/willow.egg-info"
"${PIP}" install -e "${ROOT}" --no-deps --no-build-isolation --force-reinstall

META="$("${PIP}" show willow | awk -F': ' '/^Location:/ {print $2}')"
META="${META}/willow-2.0.0.dist-info/METADATA"
if [[ -f "${META}" ]]; then
  echo "OK — installed metadata aiohttp:"
  grep -i '^Requires-Dist: aiohttp' "${META}" || true
else
  echo "OK — editable willow reinstalled (no dist-info METADATA path)"
fi
"${PIP}" check
