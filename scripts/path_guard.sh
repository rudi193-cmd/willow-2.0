#!/usr/bin/env bash
# path_guard.sh — Reject legacy home paths in tracked code (shared by CI + comfort_check).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! command -v rg >/dev/null 2>&1; then
  echo "path-guard: rg not installed — skip"
  exit 0
fi

fail=0

if rg -n '/home/[^/]+/willow-2\.0[^/]' \
    --glob '!worktrees/**' --glob '!archive/**' \
    --glob '!docs/handoffs/**' \
    --glob '!scripts/migrate_live_paths_19_to_20.py' \
    --glob '!tests/**' --glob '!**/*.md' . 2>/dev/null; then
  echo "::error::Use github/willow-2.0 or env vars, not bare ~/willow-2.0 home paths"
  fail=1
fi

if rg -n 'Path\.home\(\) / "willow-2\.0"' \
    --glob '!worktrees/**' --glob '!archive/**' \
    --glob '!tests/**' --glob '!scripts/comfort_check.sh' \
    --glob '!scripts/path_guard.sh' . 2>/dev/null; then
  echo "::error::Default WILLOW_ROOT should use github/willow-2.0 or WILLOW_HOME env"
  fail=1
fi

if [[ "${fail}" -eq 0 ]]; then
  echo "path-guard OK"
fi
exit "${fail}"
