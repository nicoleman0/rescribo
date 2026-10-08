#!/usr/bin/env bash
# Remove an issue's Herdr worktree with its database, Redis index, and branch.
# Usage: teardown-worktree.sh <issue-number> <branch> <workspace-id>
set -euo pipefail

issue=${1:?issue number required}
branch=${2:?branch name required}
workspace=${3:?herdr workspace id required}
repo=$(git rev-parse --show-toplevel)
cd "$repo"

herdr worktree remove --workspace "$workspace" >/dev/null
docker compose exec -T postgres sh -c \
  "dropdb -U \"\$POSTGRES_USER\" --if-exists rescribo_wt$issue"
docker compose exec -T redis redis-cli -n $((issue % 15 + 1)) flushdb >/dev/null
git branch -D "$branch"
git push origin --delete "$branch"
echo "Removed worktree, database rescribo_wt$issue, and branch $branch (local and remote)."
