#!/usr/bin/env bash
# Refresh editable willow metadata after pyproject.toml dependency changes.
# Fixes stale willow.egg-info (e.g. aiohttp>=3.14.1 on Python 3.14 lanes).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/.venv-dev"
[[ -x "${VENV}/bin/pip" ]] || { echo "Missing ${VENV} — run bash setup.sh first" >&2; exit 1; }
rm -rf "${ROOT}/willow.egg-info"
"${VENV}/bin/pip" install -e "${ROOT}" --no-deps --no-build-isolation --force-reinstall
echo "OK — egg-info aiohttp line:"
grep aiohttp "${ROOT}/willow.egg-info/requires.txt"
"${VENV}/bin/pip" check
