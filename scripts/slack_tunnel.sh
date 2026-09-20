#!/usr/bin/env bash
# Opens a cloudflared quick tunnel to a local feasibility receiver and prints
# the public URL to paste into the Slack app configuration.
set -euo pipefail

port="${1:-8767}"
path="${2:-/slack/interactions}"
log="$(mktemp -t slack-tunnel)"

# api.trycloudflare.com is cloudflared's own control endpoint, not the tunnel.
tunnel_hostname() {
  grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$log" | grep -v '^https://api\.' | head -1
}

cloudflared tunnel --url "http://127.0.0.1:${port}" >"$log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT

url=""
for _ in $(seq 1 60); do
  if grep -q 'failed to request quick Tunnel' "$log"; then
    echo "cloudflared could not open a tunnel:" >&2
    tail -3 "$log" >&2
    exit 1
  fi
  url="$(tunnel_hostname || true)"
  [ -n "$url" ] && break
  kill -0 "$pid" 2>/dev/null || { tail -5 "$log" >&2; exit 1; }
  sleep 1
done
[ -n "$url" ] || { echo "No tunnel URL after 60 seconds; see ${log}." >&2; exit 1; }

request_url="${url}${path}"
printf '%s' "$request_url" | pbcopy 2>/dev/null || true
echo
echo "Request URL: ${request_url}"
echo "Paste it into the app configuration, then save. Ctrl-C closes the tunnel."
wait "$pid"
