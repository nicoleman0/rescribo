#!/usr/bin/env bash
# Record a worker before prompting it, and start Herdr agents in their pane.
# Usage: start-worker.sh <issue> <role> <provider> [--turns] [-- <routing flags>...]
set -euo pipefail

issue=${1:?issue number required}
role=${2:?role required}
backend=${3:?provider required}
shift 3
turns=0
if [ "${1:-}" = --turns ]; then turns=1; shift; fi
if [ "${1:-}" = -- ]; then shift; fi
script_dir=$(cd "$(dirname "$0")" && pwd)
skill_dir=$(cd "$script_dir/.." && pwd)
[ -f "$skill_dir/roles/$role.md" ] || { echo "Unknown role: $role" >&2; exit 1; }
if [[ ! "$backend" =~ ^[a-z][a-z0-9_-]*$ ]] || ! type -P "$backend" >/dev/null 2>&1; then
  echo "Unknown provider: $backend is not a command on PATH. A provider is named after its CLI command." >&2
  exit 1
fi
state="$script_dir/state.py"
runner=$(python3 "$state" get "$issue" runner)
path=$(python3 "$state" get "$issue" path)
case "$runner" in herdr|headless) ;; *) echo "Unknown runner: $runner" >&2; exit 1 ;; esac
pane=""
if [ "$runner" = herdr ]; then pane=$(python3 "$state" get "$issue" pane); fi

extra=()
if [ "$role" = implementer ]; then extra=("implementer_backend=$backend"); fi
if [ "$role" = reviewer ]; then
  # An independent review needs a provider other than the one that wrote the code.
  built_on=$(python3 "$state" get "$issue" implementer_backend 2>/dev/null || true)
  [ -n "$built_on" ] || { echo "Issue $issue: no implementer has run, so there is nothing to review" >&2; exit 1; }
  if [ "$backend" = "$built_on" ] && [ "${SWITCHYARD_SAME_PROVIDER:-}" != 1 ]; then
    echo "Issue $issue: the implementer ran on $backend. Review on another provider, or set SWITCHYARD_SAME_PROVIDER=1" >&2
    exit 1
  fi
fi

worker=""
session=""
if [ "$runner" = headless ] || [ "$turns" = 1 ]; then
  session=$(python3 -c 'import uuid; print(uuid.uuid4())')
elif [ "$runner" = herdr ]; then
  worker="$role-$issue"
  herdr agent start "$worker" --kind "$backend" --pane "$pane" -- "$@" >/dev/null
fi

python3 "$state" set "$issue" "role=$role" "backend=$backend" "worker=$worker" "session=$session" ${extra[@]+"${extra[@]}"}
printf 'path=%s\n' "$path"
[ -z "$pane" ] || printf 'pane=%s\n' "$pane"
[ -z "$worker" ] || printf 'name=%s\n' "$worker"
[ -z "$session" ] || printf 'session=%s\n' "$session"
