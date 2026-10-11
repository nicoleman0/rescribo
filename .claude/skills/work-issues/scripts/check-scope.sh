#!/usr/bin/env bash
# List files an issue's branch changed outside the paths it owns. Exits 1 if any.
# The change's own files under openspec/ are always in scope.
# Usage: check-scope.sh <issue-number>
set -euo pipefail

issue=${1:?issue number required}
state="$(cd "$(dirname "$0")" && pwd)/state.py"
path=$(python3 "$state" get "$issue" path)
owned=$(python3 "$state" get "$issue" owned)
read -r -a prefixes <<<"$owned"

outside=()
while IFS= read -r file; do
  inside=0
  for prefix in openspec/ "${prefixes[@]}"; do
    case "$file" in "$prefix"*) inside=1 ;; esac
  done
  [ "$inside" = 1 ] || outside+=("$file")
done < <(git -C "$path" diff --name-only origin/main...HEAD)

if [ "${#outside[@]}" -gt 0 ]; then
  echo "Issue $issue changed files outside its owned paths ($owned):" >&2
  printf '%s\n' "${outside[@]}"
  exit 1
fi
echo "Issue $issue: every changed file is in scope."
