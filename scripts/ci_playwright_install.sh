#!/usr/bin/env bash
# Installs Chromium and its OS packages for Playwright, run from the package directory.
# The Ubuntu mirror sometimes trickles so slowly that apt-get never times out; bound each
# attempt and retry instead of letting one hang use up the whole job.
set -uo pipefail

attempts=2
per_attempt="${PLAYWRIGHT_INSTALL_TIMEOUT:-6m}"

# timeout cannot signal the apt-get that Playwright runs through sudo, and a survivor
# holds the dpkg lock against the retry.
stop_apt() {
  sudo pkill -KILL -x apt-get
  sudo pkill -KILL -x dpkg
  while pgrep -x apt-get >/dev/null || pgrep -x dpkg >/dev/null; do sleep 1; done
  sudo dpkg --configure -a
}

for attempt in $(seq 1 "$attempts"); do
  timeout --kill-after=30s "$per_attempt" npx playwright install --with-deps chromium && exit 0
  echo "::warning::Playwright install attempt $attempt of $attempts failed or timed out"
  stop_apt
done
echo "::error::Playwright install failed after $attempts attempts"
exit 1
