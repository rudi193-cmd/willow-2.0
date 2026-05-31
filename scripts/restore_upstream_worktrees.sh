#!/usr/bin/env bash
# Restore upstream steward clones with open PRs under worktrees/.
# See scripts/upstream_worktree_allowlist.txt and CONTRIBUTORS.md.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$ROOT/scripts/restore_upstream_worktrees.py" "$@"
