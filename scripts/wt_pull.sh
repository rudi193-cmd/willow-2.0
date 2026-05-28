#!/usr/bin/env bash
# wt_pull.sh — heartbeat pull for remote wt/* branches into .wt/incoming/
# Fetches origin/wt/* and lands each branch as a detached worktree under
# .wt/incoming/<task> — readable, not auto-merged. Requires explicit review.
#
# Cron: */5 * * * * /home/sean-campbell/willow-2.0/scripts/wt_pull.sh
# b17: WTP02  ΔΣ=42

set -euo pipefail

REPO_ROOT="${WT_REPO_ROOT:-$HOME/github}"
LOG="${WT_PULL_LOG:-/tmp/wt_pull.log}"

log() { echo "[$(date -Is)] $*" >> "$LOG"; }

find "$REPO_ROOT" -maxdepth 3 -name "worktrees" -type d | while read -r wt_root; do
    repo=$(dirname "$wt_root")
    cd "$repo"

    # fetch all remote wt/* branches
    git fetch origin 'refs/wt/*:refs/remotes/origin/wt/*' >> "$LOG" 2>&1 || {
        log "fetch failed for $repo — skipping"
        continue
    }

    git branch -r 2>/dev/null \
        | grep "origin/wt/" \
        | sed 's|.*origin/wt/||' \
        | while read -r task; do

        incoming="$wt_root/incoming/$task"  # lands at <repo>/worktrees/incoming/<task>

        if [[ -d "$incoming" ]]; then
            # already exists — update the detached checkout in place
            cd "$incoming"
            git fetch origin "wt/$task" >> "$LOG" 2>&1
            git checkout --detach "origin/wt/$task" >> "$LOG" 2>&1 \
                && log "updated incoming/$task in $repo" \
                || log "ERROR: update failed for incoming/$task in $repo"
            cd "$repo"
        else
            # new branch — add as detached worktree (no local branch created)
            mkdir -p "$wt_root/incoming"
            git worktree add --detach "$incoming" "origin/wt/$task" >> "$LOG" 2>&1 \
                && log "new incoming/$task in $repo" \
                || log "ERROR: worktree add failed for $task in $repo"
        fi
    done
done
