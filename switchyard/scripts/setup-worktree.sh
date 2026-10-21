#!/usr/bin/env bash
# Create a worktree for one issue, then run the project's up hook to isolate it.
# Inside Herdr the worktree opens as a workspace; otherwise it is a plain git
# worktree beside the checkout. The branch starts from the checkout's branch.
# Usage: setup-worktree.sh <issue-number> <branch>
set -euo pipefail

issue=${1:?issue number required}
branch=${2:?branch name required}
repo=$(git rev-parse --show-toplevel)
cd "$repo"
base=$(git symbolic-ref --short HEAD)
hook=switchyard/hooks/worktree-up.sh

if [ "${HERDR_ENV:-}" = 1 ]; then
  created=$(herdr worktree create --cwd "$repo" --branch "$branch" --base "$base" \
    --label "#$issue $branch" --no-focus)
  read -r path pane workspace < <(python3 -c '
import json, sys
r = json.load(sys.stdin)["result"]["root_pane"]
print(r["cwd"], r["pane_id"], r["workspace_id"])' <<<"$created")
  printf 'path=%s\npane=%s\nworkspace=%s\n' "$path" "$pane" "$workspace"
else
  path="$(dirname "$repo")/$(basename "$repo").worktrees/$branch"
  git worktree add --quiet -b "$branch" "$path" "$base"
  printf 'path=%s\n' "$path"
fi

# Workers never push. Only the main checkout can reach the remote.
git config extensions.worktreeConfig true
git -C "$path" config --worktree remote.origin.pushurl workers-do-not-push

state_args=(init "$issue" "branch=$branch" "path=$path")
if [ "${HERDR_ENV:-}" = 1 ]; then
  state_args+=(runner=herdr "pane=$pane")
else
  state_args+=(runner=headless)
fi
python3 switchyard/scripts/state.py "${state_args[@]}"

if [ -x "$hook" ]; then
  ISSUE=$issue BRANCH=$branch WORKTREE=$path MAIN_CHECKOUT=$repo "$hook"
fi
