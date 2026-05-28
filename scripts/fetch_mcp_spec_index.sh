#!/usr/bin/env bash
# Refresh local MCP spec index (for offline/agent reference). Pin version in sap/MCP_SPEC.lock.json.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/sap/spec/mcp-llms.txt"
mkdir -p "$(dirname "$OUT")"
curl -fsSL "https://modelcontextprotocol.io/llms.txt" -o "$OUT"
echo "Wrote ${OUT} ($(wc -l < "$OUT") lines)"
