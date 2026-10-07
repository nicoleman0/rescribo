#!/usr/bin/env bash
# Installs Chromium and its OS packages for Playwright, run from the package directory.
# The Ubuntu mirror sometimes hangs apt-get; bound each attempt and retry instead of
# letting one hang use up the whole job.
set -uo pipefail

attempts=2
per_attempt="${PLAYWRIGHT_INSTALL_TIMEOUT:-6m}"

for attempt in $(seq 1 "$attempts"); do
  timeout --kill-after=30s "$per_attempt" npx playwright install --with-deps chromium && exit 0
  echo "::warning::Playwright install attempt $attempt of $attempts failed or timed out"
done
echo "::error::Playwright install failed after $attempts attempts"
exit 1
