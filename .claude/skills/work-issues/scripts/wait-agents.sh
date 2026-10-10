#!/usr/bin/env bash
# Block until a Herdr agent needs the coordinator, then print its name and state.
# Usage: wait-agents.sh [agent-name ...]   (no names: every named agent)
set -euo pipefail

while true; do
  if herdr agent list | python3 -c '
import json, sys

names = set(sys.argv[1:])
agents = [a for a in json.load(sys.stdin)["result"]["agents"] if a.get("name")]
missing = names - {a["name"] for a in agents}
if missing:
    sys.exit(f"No such Herdr agent: {sorted(missing)}")
stopped = [a for a in agents
           if (not names or a["name"] in names)
           and a["agent_status"] in ("idle", "done", "blocked", "unknown")]
for a in stopped:
    print(a["name"], a["agent_status"])
sys.exit(0 if stopped else 3)' "$@"; then
    exit 0
  else
    status=$?
    # 3: every watched agent is still working.
    [ "$status" -eq 3 ] || exit "$status"
  fi
  sleep 15
done
