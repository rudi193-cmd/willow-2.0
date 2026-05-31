#!/usr/bin/env bash
# List remote branches idle longer than N days (default 90). Does not delete.
set -euo pipefail

DAYS="${1:-90}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! git remote get-url origin &>/dev/null; then
  echo "No origin remote — skip"
  exit 0
fi

git fetch origin --prune --quiet

now="$(date +%s)"
cutoff_epoch=$((now - DAYS * 86400))

echo "==> Remote branches with no commit in the last ${DAYS} days (excluding master/main)"
echo

count=0
while IFS= read -r ref; do
  [[ "$ref" == "origin" || "$ref" == "origin/HEAD" ]] && continue
  [[ "$ref" == origin/* ]] || continue
  branch="${ref#origin/}"
  case "$branch" in
    master|main) continue ;;
  esac
  ts="$(git log -1 --format=%ct "origin/${branch}" 2>/dev/null || echo 0)"
  if [ "$ts" -lt "$cutoff_epoch" ]; then
    age="$(( (now - ts) / 86400 ))"
    last="$(git log -1 --format='%cs %h %s' "origin/${branch}" 2>/dev/null || echo '?')"
    printf '  %4dd  %-40s  %s\n' "$age" "$branch" "$last"
    count=$((count + 1))
  fi
done < <(git for-each-ref --format='%(refname:short)' refs/remotes/origin)

echo
echo "Listed: ${count} stale branch(es). Review before deleting: git push origin --delete <branch>"
