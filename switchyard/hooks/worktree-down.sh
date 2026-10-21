#!/usr/bin/env bash
# Project hook: drop the issue's database and flush its Redis index.
# Runs from the main checkout before the worktree is removed, with ISSUE,
# BRANCH, WORKTREE, and MAIN_CHECKOUT set.
set -euo pipefail

redis_index=$(python3 "$MAIN_CHECKOUT/switchyard/hooks/redis_index.py" held "$ISSUE")
if [ -n "$redis_index" ] && [ -f "$WORKTREE/.env" ]; then
  env_index=$(python3 - "$WORKTREE/.env" <<'EOF'
import re
import sys

text = open(sys.argv[1]).read()
matches = re.findall(r"^RESCRIBO_REDIS_URL=.*?/(\d+)\s*$", text, re.M)
if len(matches) != 1:
    raise SystemExit(f"Expected one RESCRIBO_REDIS_URL with a database index in {sys.argv[1]}")
print(matches[0])
EOF
  )
  if [ "$redis_index" != "$env_index" ]; then
    echo "Issue $ISSUE record holds Redis index $redis_index but $WORKTREE/.env uses $env_index. Fix with: state.py set $ISSUE redis_index=$env_index" >&2
    exit 1
  fi
fi

docker compose exec -T postgres sh -c \
  "dropdb -U \"\$POSTGRES_USER\" --if-exists rescribo_wt$ISSUE"
if [ -z "$redis_index" ]; then
  echo "Issue $ISSUE has no recorded Redis index; skipping Redis flush." >&2
else
  docker compose exec -T redis redis-cli -n "$redis_index" flushdb >/dev/null
fi
