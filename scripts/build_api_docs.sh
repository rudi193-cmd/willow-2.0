#!/usr/bin/env bash
# Generate HTML API reference for first-party Python packages (local dev).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="${ROOT}/docs/api"

PDOC="${PDOC:-pdoc}"
if ! command -v "$PDOC" &>/dev/null; then
  for candidate in "${ROOT}/.venv-dev/bin/pdoc" "${ROOT}/.venv/bin/pdoc"; do
    if [[ -x "$candidate" ]]; then
      PDOC="$candidate"
      break
    fi
  done
fi

if ! command -v "$PDOC" &>/dev/null && [[ ! -x "$PDOC" ]]; then
  echo "pdoc not installed — run: pip install pdoc"
  exit 1
fi

rm -rf "$OUT"
mkdir -p "$OUT"

echo "==> pdoc → ${OUT}"
"$PDOC" core sap willow -o "$OUT" --docformat google
echo "Open: file://${OUT}/index.html"
