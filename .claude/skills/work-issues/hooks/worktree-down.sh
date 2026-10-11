#!/usr/bin/env bash
# Project hook: drop the issue's database and flush its Redis index.
# Runs from the main checkout before the worktree is removed, with ISSUE,
# BRANCH, WORKTREE, and MAIN_CHECKOUT set.
set -euo pipefail

docker compose exec -T postgres sh -c \
  "dropdb -U \"\$POSTGRES_USER\" --if-exists rescribo_wt$ISSUE"
docker compose exec -T redis redis-cli -n $((ISSUE % 15 + 1)) flushdb >/dev/null
