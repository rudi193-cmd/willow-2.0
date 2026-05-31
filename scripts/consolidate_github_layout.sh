#!/usr/bin/env bash
# Wire fleet home symlinks and move stray paths under ~/github/.
# Idempotent — safe to re-run. See ~/github/README-fleet-layout.md
set -euo pipefail

HOME_DIR="${HOME}"
GITHUB="${HOME_DIR}/github"
WILLOW_HOME="${GITHUB}/.willow"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN=0
REMOVE_STALE=0

usage() {
  sed -n '2,5p' "$0"
  echo "  -n | --dry-run        print actions only"
  echo "  --remove-stale        rm stale github/ clones (wt-grove-bidir, ai_news.db)"
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--dry-run) DRY_RUN=1; shift ;;
    --remove-stale) REMOVE_STALE=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown: $1" >&2; usage 1 ;;
  esac
done

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    echo "+ $*"
    "$@"
  fi
}

clear_link_path() {
  local link="$1"
  if [[ ! -e "$link" ]]; then
    return 0
  fi
  if [[ -L "$link" ]]; then
    run rm -f "$link"
    return 0
  fi
  if [[ -d "$link" ]]; then
    local entries
    entries="$(find "$link" -mindepth 1 -maxdepth 1 2>/dev/null | wc -l | tr -d ' ')"
    if [[ "$entries" == "0" ]]; then
      run rmdir "$link"
      return 0
    fi
    # Prior failed run: empty dir with nested symlink only (e.g. ~/sean-data-vault/sean-data-vault)
    if [[ "$entries" == "1" ]]; then
      local only
      only="$(find "$link" -mindepth 1 -maxdepth 1 2>/dev/null | head -1)"
      if [[ -L "$only" ]]; then
        run rm -rf "$link"
        return 0
      fi
    fi
    echo "SKIP (real dir, not empty): $link"
    return 1
  fi
  echo "SKIP (exists, not dir/symlink): $link"
  return 1
}

link_if_missing() {
  local target="$1" link="$2"
  if [[ -L "$link" ]] && [[ "$(readlink -f "$link")" == "$(readlink -f "$target")" ]]; then
    echo "OK (already linked): $link -> $target"
    return 0
  fi
  if [[ -e "$link" && ! -L "$link" ]]; then
    clear_link_path "$link" || return 0
  fi
  run ln -sfn "$target" "$link"
}

move_into_github() {
  local src="$1" dest="$2" backlink="$3"
  if [[ ! -e "$src" ]]; then
    echo "skip missing: $src"
    return 0
  fi
  if [[ -L "$src" ]]; then
    echo "skip symlink: $src -> $(readlink "$src")"
    return 0
  fi
  if [[ "$src" == "$dest" || "$(readlink -f "$src")" == "$(readlink -f "$dest")" ]]; then
    echo "OK (already at dest): $dest"
    link_if_missing "$dest" "$backlink"
    return 0
  fi
  if [[ -e "$dest" ]]; then
    if [[ -d "$src" ]] && [[ -z "$(ls -A "$src" 2>/dev/null || true)" ]]; then
      echo "Removing empty source after prior migrate: $src"
      run rmdir "$src" 2>/dev/null || true
    else
      echo "WARN dest exists — wiring backlink only: $dest"
    fi
    if [[ -n "$backlink" ]]; then
      link_if_missing "$dest" "$backlink"
    fi
    return 0
  fi
  run mkdir -p "$(dirname "$dest")"
  if mv "$src" "$dest" 2>/dev/null; then
    :
  else
    echo "WARN mv busy — rsync then remove source: $src"
    run rsync -a "$src/" "$dest/"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      rm -rf "$src" 2>/dev/null || echo "  (source still present — close handles and rm -rf $src manually)"
    fi
  fi
  if [[ -n "$backlink" ]]; then
    link_if_missing "$dest" "$backlink"
  fi
}

# When ~/name and ~/github/<dest_name> both exist, keep github copy and replace ~ with symlink.
dedupe_home_clone() {
  local name="$1"
  local dest_sub="${2:-$name}"
  local src="${HOME_DIR}/${name}"
  local dest="${GITHUB}/${dest_sub}"
  local backlink="${HOME_DIR}/${name}"

  if [[ ! -e "$src" ]]; then
    return 0
  fi
  if [[ -L "$src" ]]; then
    echo "OK (already symlink): ${backlink}"
    return 0
  fi
  if [[ ! -e "$dest" ]]; then
    move_into_github "$src" "$dest" "$backlink"
    return 0
  fi
  echo "==> dedupe ~/${name} → github/${dest_sub}"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] rm -rf ${src} && ln -sfn ${dest} ${backlink}"
    return 0
  fi
  if rm -rf "$src" 2>/dev/null; then
    :
  else
    echo "  WARN busy — close handles then: rm -rf ${src} && ln -sfn ${dest} ${backlink}"
    return 0
  fi
  run ln -sfn "$dest" "$backlink"
}

echo "==> Side repos at ~ → ~/github/* (or dedupe if already under github/)"
SIDE_REPOS=(
  claude-deep-review
  litellm
  ngrok-python
  python-sdk
)
for name in "${SIDE_REPOS[@]}"; do
  dedupe_home_clone "$name"
done

echo "==> Personal / small trees"
dedupe_home_clone "journal" "sean-data-vault/journal"

echo "==> Stale worktrees → ~/github/archive/"
mkdir -p "${GITHUB}/archive"
ARCHIVE_REPOS=(
  willow-2.0-wt-grove-bidir
  willow-wt
)
for name in "${ARCHIVE_REPOS[@]}"; do
  dedupe_home_clone "$name" "archive/${name}"
done

echo "==> Fleet symlinks (legacy paths -> ~/github/*)"
mkdir -p "${GITHUB}/SAFE/Applications" "${GITHUB}/SAFE/Agents"
link_if_missing "${WILLOW_HOME}" "${HOME_DIR}/.willow"
link_if_missing "${GITHUB}/SAFE" "${HOME_DIR}/SAFE"
link_if_missing "${REPO_ROOT}" "${HOME_DIR}/willow-2.0"
if [[ -d "${GITHUB}/safe-app-store" ]]; then
  link_if_missing "${GITHUB}/safe-app-store" "${HOME_DIR}/safe-app-store"
fi

echo "==> Move personal/archive trees into ~/github/"
move_into_github "${HOME_DIR}/sean-data-vault" "${GITHUB}/sean-data-vault" "${HOME_DIR}/sean-data-vault"
move_into_github "${HOME_DIR}/agents" "${GITHUB}/archive/legacy-agents-home" "${HOME_DIR}/agents"

echo "==> willow-2.0 repo drops (untracked cruft -> sean-data-vault/repo-drops)"
DROPS="${GITHUB}/sean-data-vault/repo-drops/willow-2.0"
for name in Ashokoa personal; do
  src="${REPO_ROOT}/${name}"
  if [[ -d "$src" && ! -L "$src" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "[dry-run] mv $src -> ${DROPS}/${name}"
    else
      run mkdir -p "$DROPS"
      run mv "$src" "${DROPS}/${name}"
    fi
  fi
done
if [[ -L "${REPO_ROOT}/dashboard-fresh" ]]; then
  run rm -f "${REPO_ROOT}/dashboard-fresh"
fi

echo "==> Optional github/ cleanup (stale clones — pass --remove-stale)"
if [[ "$REMOVE_STALE" -eq 1 ]]; then
  for d in safe-app-willow-grove-wt-grove-bidir; do
    path="${GITHUB}/${d}"
    [[ -d "$path" ]] && run rm -rf "$path"
  done
  [[ -f "${GITHUB}/ai_news.db" ]] && run rm -f "${GITHUB}/ai_news.db"
fi

echo "==> link_fleet_home (willow.md + config into repo)"
if [[ "$DRY_RUN" -eq 0 ]]; then
  (cd "$REPO_ROOT" && PYTHONPATH="$REPO_ROOT" python3 -m willow.fylgja.link_fleet_home)
fi

echo "==> Summary"
for p in .willow SAFE willow-2.0 safe-app-store sean-data-vault agents \
  claude-deep-review journal litellm ngrok-python python-sdk \
  willow-2.0-wt-grove-bidir willow-wt; do
  f="${HOME_DIR}/${p}"
  if [[ -L "$f" ]]; then
    echo "  ~/${p} -> $(readlink "$f")"
  elif [[ -e "$f" ]]; then
    du -sh "$f" 2>/dev/null | awk -v n="$p" '{print "  ~/" n " (real dir) " $1}'
  fi
done
echo "Done."
