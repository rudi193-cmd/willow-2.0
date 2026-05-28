#!/usr/bin/env bash
# wt_push.sh — heartbeat push for all in-repo worktrees
# Scans $WT_REPO_ROOT for repos with worktrees/ dirs, PII-checks each unpushed
# branch, and pushes clean branches to origin/wt/<branch>.
#
# Cron: */5 * * * * /home/sean-campbell/github/willow-2.0/scripts/wt_push.sh
# b17: WTP01  ΔΣ=42

set -euo pipefail

REPO_ROOT="${WT_REPO_ROOT:-$HOME/github}"
PII_CHECK="${WILLOW_REPO:-$HOME/github/willow-2.0}/scripts/pii_check.py"
LOG="${WT_PUSH_LOG:-/tmp/wt_push.log}"

log() { echo "[$(date -Is)] $*" >> "$LOG"; }

if [[ ! -f "$PII_CHECK" ]]; then
    log "ERROR: pii_check.py not found at $PII_CHECK"
    exit 1
fi

find "$REPO_ROOT" -maxdepth 3 -name "worktrees" -type d | while read -r wt_root; do
    repo=$(dirname "$wt_root")
    cd "$repo"

    git worktree list --porcelain \
        | grep "^worktree " | awk '{print $2}' \
        | grep "^$repo/worktrees/" \
        | grep -v "^$repo/worktrees/incoming" \
        | while read -r wt_path; do

        branch=$(cd "$wt_path" && git branch --show-current 2>/dev/null) || continue
        [[ -z "$branch" ]] && continue

        # check if remote tracking branch exists (one ls-remote, reused below)
        if git ls-remote --exit-code origin "wt/$branch" &>/dev/null; then
            has_remote=1
            unpushed=$(cd "$wt_path" && git log --oneline "origin/wt/$branch..HEAD" 2>/dev/null | wc -l) || continue
        else
            has_remote=0
            unpushed=$(cd "$wt_path" && git log --oneline "$(git merge-base HEAD origin/master 2>/dev/null || git rev-list --max-parents=0 HEAD)..HEAD" 2>/dev/null | wc -l) || continue
        fi

        [[ "$unpushed" -eq 0 ]] && continue

        log "checking $wt_path (branch=$branch, $unpushed unpushed commit(s))"

        # diff only the unpushed delta — cap at 50 commits for new branches
        diff=$(cd "$wt_path" && {
            if [[ "$has_remote" -eq 1 ]]; then
                git diff "origin/wt/$branch..HEAD" 2>/dev/null
            else
                git diff "HEAD~$(( unpushed < 50 ? unpushed : 50 ))..HEAD" 2>/dev/null
            fi
        }) || continue

        if echo "$diff" | python3 "$PII_CHECK" 2>>"$LOG"; then
            cd "$wt_path"
            git push origin "HEAD:wt/$branch" >> "$LOG" 2>&1 \
                && log "pushed $branch → origin/wt/$branch" \
                || log "ERROR: push failed for $branch"
            cd "$repo"
        else
            log "PII gate blocked push for $branch — fix and retry"
        fi
    done
done
