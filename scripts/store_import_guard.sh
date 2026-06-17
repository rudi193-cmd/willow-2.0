#!/usr/bin/env bash
# store_import_guard.sh — Reject direct WillowStore imports outside allowlist (ADR-20260616 Phase 3).
# b17: STGRD · ΔΣ=42
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! command -v rg >/dev/null 2>&1; then
  echo "store-import-guard: rg not installed — skip"
  exit 0
fi

fail=0

_pattern='from (core\.)?willow_store import WillowStore|from willow_store import WillowStore'

# Phase 2: willow/fylgja must use StorePort — zero tolerance.
if rg -n "${_pattern}" willow/fylgja --glob '*.py' 2>/dev/null; then
  echo "::error::willow/fylgja must use core.store_port.get_store_port(), not WillowStore"
  fail=1
fi

# Fleet modules outside grandfathered scripts/tests — incremental enforcement.
# scripts/** grandfathered per ADR; metabolic/inference paths migrate when touched.
if rg -n "${_pattern}" \
    --glob '*.py' \
    --glob '!core/willow_store.py' \
    --glob '!core/store_port.py' \
    --glob '!core/soil.py' \
    --glob '!sap/sap_mcp.py' \
    --glob '!scripts/**' \
    --glob '!tests/**' \
    --glob '!archive/**' \
    --glob '!worktrees/**' \
    --glob '!willow/fylgja/**' \
    --glob '!willow/grove_coordination.py' \
    --glob '!willow/hns_enforcer.py' \
    --glob '!willow/hns_scheduler.py' \
    --glob '!core/metabolic.py' \
    --glob '!core/inference_router.py' \
    --glob '!core/graceful.py' \
    . 2>/dev/null; then
  echo "::error::Direct WillowStore import outside allowlist — use StorePort, core.soil, or SoilClient"
  fail=1
fi

if [[ "${fail}" -eq 0 ]]; then
  echo "store-import-guard OK"
fi
exit "${fail}"
