#!/usr/bin/env bash
# End a Herdr agent and leave its pane ready for the next command.
# Usage: end-worker.sh <issue>
set -euo pipefail

issue=${1:?issue number required}
script_dir=$(cd "$(dirname "$0")" && pwd)
skill_dir=$(cd "$script_dir/.." && pwd)
state="$script_dir/state.py"
runner=$(python3 "$state" get "$issue" runner)
[ "$runner" = herdr ] || { echo "Issue $issue: End is only available on the Herdr runner" >&2; exit 1; }
pane=$(python3 "$state" get "$issue" pane)
worker=$(python3 "$state" get "$issue" worker 2>/dev/null || true)
backend=$(python3 "$state" get "$issue" backend)
if [ -z "$worker" ]; then
  echo "Issue $issue: there is no agent to end"
  exit 0
fi

get_agent() {
  herdr agent get "$worker" 2>&1
}

agent_result=$(get_agent) || agent_status=$?
if [ "${agent_status:-0}" -ne 0 ]; then
  if ! [[ "$agent_result" == *agent_not_found* ]]; then
    echo "$agent_result" >&2
    exit 1
  fi
else
  status=$(python3 -c 'import json,sys; r=json.load(sys.stdin).get("result", {}); a=r.get("agent", r); print(a.get("agent_status", ""))' <<<"$agent_result")
  case "$status" in
    working|blocked) echo "Issue $issue: $worker is $status; wait for or read the agent before ending it" >&2; exit 1 ;;
  esac

  end_value=$(python3 - "$skill_dir/routing.md" "$backend" <<'PY' 2>&1
from pathlib import Path
import sys

path, provider = Path(sys.argv[1]), sys.argv[2]
if not path.is_file():
    raise SystemExit(f"routing file is missing: {path}")
lines = path.read_text().splitlines()
table = False
header = None
for line in lines:
    cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
    if not table:
        if "Provider" in cells and "End" in cells:
            header = cells
            table = True
        continue
    if line.lstrip().startswith("|"):
        if all(set(cell) <= set(":- ") for cell in cells):
            continue
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells))
        if row.get("Provider") == provider:
            value = row.get("End", "").strip()
            if value:
                print(value)
                raise SystemExit(0)
            raise SystemExit(f"End value is empty for provider {provider} in routing.md")
    elif table:
        break
raise SystemExit(f"provider {provider} or Providers table End column is missing in routing.md")
PY
) || { echo "Issue $issue: $end_value" >&2; exit 1; }
  prompt_result=$(herdr agent prompt "$worker" "$end_value" 2>&1 >/dev/null) || prompt_rc=$?
  if [ "${prompt_rc:-0}" -ne 0 ] && [[ "$prompt_result" != *agent_not_found* ]]; then
    echo "$prompt_result" >&2
    exit 1
  fi
fi

timeout=${END_WORKER_TIMEOUT_SECONDS:-30}
[[ "$timeout" =~ ^[1-9][0-9]*$ ]] || { echo "Issue $issue: END_WORKER_TIMEOUT_SECONDS must be a positive integer" >&2; exit 1; }
last_state=${status:-agent_not_found}
for ((elapsed=0; elapsed<timeout; elapsed++)); do
  agent_status=0
  agent_result=$(get_agent) || agent_status=$?
  if [ "$agent_status" -eq 0 ]; then
    last_state=$(python3 -c 'import json,sys; r=json.load(sys.stdin).get("result", {}); a=r.get("agent", r); print(a.get("agent_status", "unknown"))' <<<"$agent_result")
  else
    if [[ "$agent_result" == *agent_not_found* ]]; then
      pane_result=$(herdr pane process-info --pane "$pane") || { echo "$pane_result" >&2; exit 1; }
      read -r shell_pid foreground_pid < <(python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("result", d); r=r.get("process_info", r); print(r["shell_pid"], r["foreground_process_group_id"])' <<<"$pane_result")
      last_state=agent_not_found
      if [ "$shell_pid" = "$foreground_pid" ]; then
        herdr pane send-keys "$pane" ctrl+u >/dev/null 2>&1
        printf 'ended=%s\n' "$worker"
        exit 0
      fi
    else
      echo "$agent_result" >&2
      exit 1
    fi
  fi
  sleep 1
done
echo "Issue $issue: timed out ending $worker; last state: $last_state" >&2
exit 1
