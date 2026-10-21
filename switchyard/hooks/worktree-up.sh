#!/usr/bin/env bash
# Project hook: give one issue's worktree its own database, Redis index, and ports.
# Runs from the main checkout with ISSUE, BRANCH, WORKTREE, and MAIN_CHECKOUT set.
# Print key=value lines on stdout for the brief. Send everything else to stderr.
set -euo pipefail

docker compose exec -T postgres true >&2 || {
  echo "Postgres is not running. Run task services in $MAIN_CHECKOUT first." >&2
  exit 1
}

suffix=$(printf '%03d' $((ISSUE % 1000)))
api="8$suffix"
web="5$suffix"
redis_index=$(python3 "$MAIN_CHECKOUT/switchyard/hooks/redis_index.py" claim "$ISSUE")
database="rescribo_wt$ISSUE"

docker compose exec -T postgres sh -c \
  "createdb -U \"\$POSTGRES_USER\" $database 2>/dev/null || true" >&2

# Ports and origins follow the frontend port. Playwright reads its ports from
# the environment, not this file.
python3 - "$MAIN_CHECKOUT/.env" "$WORKTREE/.env" "$database" "$redis_index" "$web" <<'EOF'
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

(cd "$WORKTREE" && task install && task migrate) >&2

printf 'api=%s\nweb=%s\ndatabase=%s\nredis_index=%s\n' "$api" "$web" "$database" "$redis_index"
