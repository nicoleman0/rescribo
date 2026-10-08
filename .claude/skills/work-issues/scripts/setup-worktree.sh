#!/usr/bin/env bash
# Create an isolated Herdr worktree for one issue: own branch, database, Redis
# index, and ports, so parallel checks never share state.
# Usage: setup-worktree.sh <issue-number> <branch>
set -euo pipefail

issue=${1:?issue number required}
branch=${2:?branch name required}
repo=$(git rev-parse --show-toplevel)
cd "$repo"

if [ "${HERDR_ENV:-}" != 1 ]; then
  echo "Run this from a Herdr pane (HERDR_ENV=1)." >&2
  exit 1
fi
docker compose exec -T postgres true || {
  echo "Postgres is not running. Run task services in $repo first." >&2
  exit 1
}

suffix=$(printf '%03d' $((issue % 1000)))
api="8$suffix"
web="5$suffix"
redis_index=$((issue % 15 + 1))
database="rescribo_wt$issue"

created=$(herdr worktree create --cwd "$repo" --branch "$branch" --base main \
  --label "#$issue $branch" --no-focus)
read -r path pane workspace < <(python3 -c '
import json, sys
r = json.load(sys.stdin)["result"]["root_pane"]
print(r["cwd"], r["pane_id"], r["workspace_id"])' <<<"$created")

docker compose exec -T postgres sh -c \
  "createdb -U \"\$POSTGRES_USER\" $database 2>/dev/null || true"

# Ports and origins follow the frontend port; the database and Redis index are
# per issue. Playwright reads its ports from the environment, not this file.
python3 - "$repo/.env" "$path/.env" "$database" "$redis_index" "$web" <<'EOF'
import re
import sys

source, target, database, redis_index, web = sys.argv[1:]
text = open(source).read()
rules = [
    (r"^(RESCRIBO_DATABASE_URL=.*/)[^/\n]+$", rf"\g<1>{database}"),
    (r"^(RESCRIBO_REDIS_URL=.*/)\d+$", rf"\g<1>{redis_index}"),
    (r"^DJANGO_CSRF_TRUSTED_ORIGINS=.*$",
     f"DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:{web},http://127.0.0.1:{web}"),
    (r"^RESCRIBO_PUBLIC_BASE_URL=.*$", f"RESCRIBO_PUBLIC_BASE_URL=http://127.0.0.1:{web}"),
]
for pattern, replacement in rules:
    text, count = re.subn(pattern, replacement, text, flags=re.M)
    assert count == 1, f"{pattern} matched {count} lines in {source}"
open(target, "w").write(text)
EOF

(cd "$path" && task install && task migrate) >/dev/null

printf 'path=%s\npane=%s\nworkspace=%s\napi=%s\nweb=%s\ndatabase=%s\nredis_index=%s\n' \
  "$path" "$pane" "$workspace" "$api" "$web" "$database" "$redis_index"
