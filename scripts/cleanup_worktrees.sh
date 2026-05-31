#!/usr/bin/env bash
# Remove stale git worktrees and orphan directories under worktrees/.
# Safe: only removes paths not in `git worktree list`. Does not delete remote branches.
#
# upstream-* steward clones are PROTECTED by default (see upstream_worktree_allowlist.txt).
# Remove one only with:  --remove-upstream upstream-stash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ALLOWLIST="$ROOT/scripts/upstream_worktree_allowlist.txt"
REMOVE_UPSTREAM=()

usage() {
  sed -n '2,8p' "$0"
  echo "  --remove-upstream NAME   explicitly remove worktrees/NAME (repeatable)"
  echo "  -n | --dry-run            print actions only"
  exit "${1:-0}"
}

DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--dry-run) DRY_RUN=1; shift ;;
    --remove-upstream)
      [[ $# -ge 2 ]] || usage 1
      REMOVE_UPSTREAM+=("$2")
      shift 2
      ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage 1 ;;
  esac
done

explicit_upstream_remove() {
  local base="$1"
  local t
  for t in "${REMOVE_UPSTREAM[@]}"; do
    [[ "$t" == "$base" ]] && return 0
  done
  return 1
}

rm_path() {
  local path="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  [dry-run] rm -rf $path"
    return 0
  fi
  if rm -rf "$path" 2>/dev/null; then
    return 0
  fi
  if [[ -d "$path/target" ]] && command -v sudo >/dev/null; then
    sudo chown -R "$(id -un):$(id -gn)" "$path" 2>/dev/null || true
    rm -rf "$path"
  else
    return 1
  fi
}

echo "==> Fetch + prune"
git fetch origin --prune --quiet || echo "WARN: git fetch failed (continuing with local refs)" >&2
git worktree prune -v

echo "==> Registered worktrees"
git worktree list

mapfile -t REGISTERED < <(git worktree list --porcelain | awk '/^worktree /{print $2}')

remove_orphan_dir() {
  local d="$1"
  for r in "${REGISTERED[@]}"; do
    [[ "$d" == "$r" ]] && return 1
  done
  return 0
}

echo "==> Orphan dirs under worktrees/"
removed=0
skipped_upstream=0
if [[ -d worktrees ]]; then
  for d in worktrees/*/; do
    [[ -d "$d" ]] || continue
    path="${d%/}"
    base="$(basename "$path")"
    if ! remove_orphan_dir "$ROOT/$path"; then
      continue
    fi
    if [[ "$base" == upstream-* ]]; then
      if explicit_upstream_remove "$base"; then
        echo "  rm -rf $path  (--remove-upstream)"
        rm_path "$path" && removed=$((removed + 1)) || echo "  FAILED: $path"
      else
        echo "  SKIP protected upstream: $base"
        skipped_upstream=$((skipped_upstream + 1))
      fi
      continue
    fi
    echo "  rm -rf $path"
    rm_path "$path" && removed=$((removed + 1)) || echo "  FAILED (close IDE tabs using this path, then retry)"
  done
fi

echo "Removed $removed orphan dir(s); skipped $skipped_upstream protected upstream clone(s)"

if [[ "$DRY_RUN" -eq 0 ]]; then
  echo "==> Delete local branches merged into origin/master"
  while IFS= read -r b; do
    b="${b#* }"
    [[ "$b" == "master" || "$b" == "main" || -z "$b" ]] && continue
    git branch -d "$b" 2>/dev/null && echo "  deleted $b" || true
  done < <(git branch --merged origin/master)
fi

echo "==> Done"
git worktree list
echo "worktrees/ contents: $(ls -1 worktrees 2>/dev/null | wc -l) entries"
