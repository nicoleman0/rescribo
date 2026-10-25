#!/usr/bin/env bash
# Remove an issue's worktree, branches, and per-issue state.
# Ordinary teardown refuses dirty worktrees to avoid leaving a half-torn-down issue.
# --abandon reports what it discards; missing steps are skipped.
# Usage: teardown-worktree.sh [--abandon] <issue-number> <branch>
set -euo pipefail

abandon=
while [ "${1:-}" = --abandon ]; do
  abandon=1
  shift
done
case ${1:-} in
  -*)
    echo "Unknown option $1. Usage: teardown-worktree.sh [--abandon] <issue-number> <branch>" >&2
    exit 2
    ;;
esac

issue=${1:?issue number required}
branch=${2:?branch name required}
[ $# -eq 2 ] || { echo "Usage: teardown-worktree.sh [--abandon] <issue-number> <branch>" >&2; exit 2; }
repo=$(git rev-parse --show-toplevel)
cd "$repo"
hook=switchyard/hooks/worktree-down.sh
get_err=$(mktemp)
trap 'rm -f "$get_err"' EXIT
has_record=
record_path=
if recorded_branch=$(python3 switchyard/scripts/state.py get "$issue" branch 2>"$get_err"); then
  has_record=1
  if [ "$recorded_branch" != "$branch" ]; then
    echo "Issue $issue records branch $recorded_branch, not $branch." >&2
    exit 1
  fi
  record_path=$(python3 switchyard/scripts/state.py get "$issue" path)
else
  state_status=$?
  # Status 3 is "no record"; its setup hint is wrong advice here, so drop it.
  if [ "$state_status" -ne 3 ]; then
    cat "$get_err" >&2
    exit "$state_status"
  fi
fi

entry_path=$(git worktree list --porcelain | awk -v ref="branch refs/heads/$branch" '
  /^worktree / { path = substr($0, 10) }
  $0 == ref { print path }')
path=${entry_path:-$record_path}
worktree_present=
if [ -n "$entry_path" ] && [ -d "$entry_path" ]; then
  worktree_present=1
else
  if [ -z "$entry_path" ] && [ -n "$record_path" ] && [ -d "$record_path" ]; then
    echo "No worktree has branch $branch checked out, but the recorded path exists: $record_path." >&2
    exit 1
  fi
  echo "Skipped: worktree for $branch is already gone."
fi

local_present=
if git show-ref --verify --quiet "refs/heads/$branch"; then
  local_present=1
else
  echo "Skipped: local branch $branch is already gone."
fi

remote_branch_state() {
  # ls-remote exits 2 when the named branch does not exist.
  git ls-remote --exit-code --heads origin "$1" >/dev/null
}

# Nothing to tear down: fail before the hook so a typo does not run it.
if [ -z "$has_record" ] && [ -z "$entry_path" ] && [ -z "$local_present" ]; then
  if remote_branch_state "$branch"; then
    :
  else
    status=$?
    if [ "$status" -ne 2 ]; then
      exit "$status"
    fi
    echo "Issue $issue: no record, and nothing to remove for branch $branch." >&2
    exit 1
  fi
fi

# Check before the hook so a refusal cannot leave per-issue state half removed.
if [ -n "$worktree_present" ] && [ -z "$abandon" ] && [ -n "$(git -C "$path" status --porcelain)" ]; then
  git -C "$path" status --short >&2
  echo "Worktree $path has uncommitted changes. Use --abandon to discard them." >&2
  exit 1
fi

if [ -n "$abandon" ]; then
  echo "Abandoning issue $issue. About to discard:"
  if [ -n "$worktree_present" ]; then
    echo "Uncommitted files in $path:"
    git -C "$path" status --short
  else
    echo "Worktree folder is gone."
  fi
  if [ -n "$local_present" ]; then
    echo "Commits on $branch that no remote branch has:"
    git log --oneline "$branch" --not --remotes
  else
    echo "Local branch is gone."
  fi
fi

if [ -x "$hook" ]; then
  ISSUE=$issue BRANCH=$branch WORKTREE=$path MAIN_CHECKOUT=$repo "$hook"
fi

removed=()
if [ -n "$worktree_present" ]; then
  workspace=
  if [ "${HERDR_ENV:-}" = 1 ]; then
    workspace=$(herdr worktree list --cwd "$repo" | python3 -c '
import json, sys
rows = json.load(sys.stdin)["result"]["worktrees"]
print(next((r.get("open_workspace_id") or "" for r in rows if r["branch"] == sys.argv[1]), ""))' "$branch")
  fi
  if [ -n "$workspace" ]; then
    if [ -n "$abandon" ]; then
      # Herdr requires force when the worktree has uncommitted changes.
      herdr worktree remove --workspace "$workspace" --force >/dev/null
    else
      herdr worktree remove --workspace "$workspace" >/dev/null
    fi
  elif [ -n "$abandon" ]; then
    git worktree remove --force "$path"
  else
    git worktree remove "$path"
  fi
  removed+=("worktree $path")
elif [ -n "$entry_path" ]; then
  # Remove only this issue's stale entry; prune could affect other worktrees.
  git worktree remove "$entry_path"
  removed+=("stale worktree entry $entry_path")
fi

if [ -n "$local_present" ]; then
  # Git refuses to delete a branch checked out in any worktree.
  git branch -D "$branch"
  removed+=("local branch $branch")
fi

push_failed=
if remote_branch_state "$branch"; then
  if ! git push origin --delete "$branch"; then
    # A concurrent delete can make push fail after the branch is already gone.
    if remote_branch_state "$branch"; then
      push_failed=exists
    elif [ $? -ne 2 ]; then
      push_failed=unknown
    fi
  else
    removed+=("remote branch $branch")
  fi
else
  status=$?
  if [ "$status" -eq 2 ]; then
    echo "Skipped: remote branch $branch is already gone."
  else
    exit "$status"
  fi
fi

python3 switchyard/scripts/state.py rm "$issue"
if [ -n "$push_failed" ]; then
  if [ "$push_failed" = exists ]; then
    echo "Failed to delete remote branch $branch on origin: it still exists." >&2
  else
    echo "Failed to delete remote branch $branch on origin: could not confirm it is gone." >&2
  fi
  exit 1
fi
if [ "${#removed[@]}" -gt 0 ]; then
  printf 'Removed '
  separator=
  for item in "${removed[@]}"; do
    printf '%s%s' "$separator" "$item"
    separator=', '
  done
  printf '.\n'
else
  echo "Removed issue $issue record."
fi
