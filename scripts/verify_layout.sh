#!/usr/bin/env bash
# verify_layout.sh — Repo layout and config hygiene (no systemd, no gpg).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

fail=0
warn=0

_ok() { echo "  OK: $*"; }
_fail() { echo "  FAIL: $*"; fail=$((fail + 1)); }
_warn() { echo "  WARN: $*"; warn=$((warn + 1)); }

echo "[verify_layout] repo=${ROOT}"

# Required artifacts from comfort session
for f in \
  sap/MCP_SPEC.lock.json \
  sap/mcp_registry.json \
  sap/unified_mcp.sh \
  sap/mcp_profiles.py \
  sap/mcp_enrich.py \
  scripts/check_mcp_registry.py \
  scripts/comfort_check.sh \
  docs/MCP_TOOL_PROFILES.md \
  docs/MCP_SPEC_COMPLIANCE.md \
  docs/templates/README.md \
  agents/willow/config/mcp.json.example \
  willow/fylgja/config/cursor-hooks.json \
  willow/fylgja/config/kart-sandbox.json; do
  if [[ -f "${f}" ]]; then
    _ok "${f}"
  else
    _fail "missing ${f}"
  fi
done

# Registry JSON valid
if python3 -c "import json; json.load(open('sap/mcp_registry.json'))" 2>/dev/null; then
  _ok "mcp_registry.json parses"
else
  _fail "mcp_registry.json invalid JSON"
fi

# unified MCP profile default
if grep -q 'WILLOW_MCP_PROFILE' sap/unified_mcp.sh; then
  _ok "unified_mcp.sh sets WILLOW_MCP_PROFILE"
else
  _fail "unified_mcp.sh missing WILLOW_MCP_PROFILE"
fi

# Agent MCP template (tracked example; live mcp.json is gitignored)
if grep -q 'WILLOW_MCP_PROFILE' agents/willow/config/mcp.json.example; then
  _ok "mcp.json.example has WILLOW_MCP_PROFILE"
else
  _fail "mcp.json.example missing WILLOW_MCP_PROFILE"
fi

if rg -q 'gsk_|sk-ant-|sk-proj-' agents/willow/config/mcp.json.example 2>/dev/null; then
  _fail "API key in mcp.json.example — use secrets.sh only"
else
  _ok "no API keys in mcp.json.example"
fi

mcp_live="agents/willow/config/mcp.json"
if [[ -f "${mcp_live}" ]]; then
  if grep -q 'WILLOW_MCP_PROFILE' "${mcp_live}"; then
    _ok "local mcp.json present (gitignored)"
  else
    _warn "local mcp.json missing WILLOW_MCP_PROFILE"
  fi
  keys="$(rg -l 'gsk_|sk-ant-|sk-proj-' agents/*/config/mcp.json 2>/dev/null || true)"
  if [[ -n "${keys}" ]]; then
    _warn "API key in local agents/*/config/mcp.json — move to ~/.willow/secrets.sh"
  fi
fi

# Active agent file when present
if [[ -f .willow/active-agent ]]; then
  active="$(tr -d '[:space:]' < .willow/active-agent)"
  if [[ -n "${active}" && -f "agents/${active}/config/mcp.json" ]]; then
    _ok "active-agent=${active}"
  else
    _fail "active-agent=${active} but agents/${active}/config/mcp.json missing"
  fi
else
  _warn "no .willow/active-agent (run: ./willow agents active willow)"
fi

# Cursor hooks — committed real file or legacy symlink to canonical template
if [[ -f .cursor/hooks.json && ! -L .cursor/hooks.json && -f willow/fylgja/config/cursor-hooks.json ]]; then
  if cmp -s .cursor/hooks.json willow/fylgja/config/cursor-hooks.json; then
    _ok ".cursor/hooks.json matches canonical template"
  else
    _warn ".cursor/hooks.json stale — run: python3 scripts/sync_remote_cursor_surface.py"
  fi
elif [[ -L .cursor/hooks.json ]]; then
  _ok ".cursor/hooks.json is legacy symlink"
elif [[ -f .cursor/hooks.json ]]; then
  _warn ".cursor/hooks.json present but canonical template missing"
else
  _warn ".cursor/hooks.json missing — run: python3 scripts/sync_remote_cursor_surface.py"
fi

echo "[verify_layout] fail=${fail} warn=${warn}"
[[ "${fail}" -eq 0 ]]
