# Slack message shortcut capture feasibility check

This opt-in check covers GitHub issue #3. It verifies that a Slack message shortcut opens a capture modal inside Slack's acknowledgement deadline, that submissions arrive firmly bound to the shortcut context, and that rejected source text is never retained. It does not create a production connection, persist credentials, or write raw interaction payloads to disk.

## Test app settings

Slack app inside a disposable workspace. Nothing here is reinstalled.

- **Bot token scopes, exactly these five and nothing else:** `commands`, `channels:read`, `groups:read`, `chat:write`, `im:write`.
- **Interactivity:** on. Request URL `https://<tunnel-host>/slack/interactions`.
- **Message shortcut:** one entry, name "Submit customer feedback", callback id `submit_customer_feedback`.
- Install to the workspace from the app's configuration page and copy the bot token (`xoxb-...`). No OAuth install flow is exercised; workspace install binding belongs to issue #26.

Prepare the workspace before running:

1. One approved public channel and one approved private channel with the bot invited to both.
2. One unapproved channel (used for rejection).
3. A direct message conversation with the bot (used for rejection).

## Run the check

Set these values in the shell or the gitignored `.env.slack-feasibility` file (matched by `.env.*`):

```sh
export RESCRIBO_SLACK_SIGNING_SECRET=...
export RESCRIBO_SLACK_BOT_TOKEN=xoxb-...
export RESCRIBO_SLACK_RECEIVER_URL=http://127.0.0.1:8767/slack/interactions
```

Expose the receiver to Slack with a public HTTPS tunnel:

```sh
cloudflared tunnel --url http://127.0.0.1:8767
```

Pass the origin only. `cloudflared` takes the host and scheme from `--url` and forwards the incoming path unchanged ([`httpService.RoundTrip`](https://github.com/cloudflare/cloudflared/blob/master/ingress/origin_proxy.go) sets `req.URL.Host` and `req.URL.Scheme` and nothing else), so a path written into the flag is silently ignored. The app's Request URL keeps `/slack/interactions`.

`cloudflared` quick tunnels need no account, but the printed `*.trycloudflare.com` URL changes on every run, so the app's Request URL must be updated each time. ngrok works too. smee.io does **not**: Slack expects a synchronous response body for `response_action` delivery. smee can only forward request bodies to a browser window, not return a synchronous response payload back to Slack, so `views.open` is the only reliable way to open the modal over smee and `response_action: errors` cannot work at all.

Run the check with the operator-declared channel ids. The operator declares which channel is public and which is private; the allowlist is those two ids. No `conversations.info` call is made (that belongs to issue #26):

```sh
task slack-shortcut-check -- \
  --workspace feasibility-a \
  --workspace-name "Feasibility A" \
  --public-channel C0PUBLIC \
  --private-channel C0PRIVATE \
  [--fail-first-submission]
```

What the check does, in order:

1. Verifies the bot token with `auth.test` and asserts that the granted scopes are exactly the five proposed. Anything else fails the check before a request is served.
2. Starts a threading loopback receiver. Threading is required because Slack retries any interaction that is not answered within three seconds; a single-threaded handler would queue a retry behind a slow `views.open`.
3. Waits for interaction requests. Every request's signature and timestamp are verified against the raw body before parsing; bad signatures answer 401.
4. Per `message_action` shortcut: the source channel is checked against the operator-supplied allowlist. Rejections (DM or unapproved channel) are recorded with `text_retained: false` and the message text is dropped without being copied anywhere. Approved shortcuts mint an opaque context id, build the capture modal, call `views.open` inside the acknowledgement window, and answer 200. A duplicate capture inside one run is recorded as `duplicate: true`, not counted as new coverage.
5. Per `view_submission`: the context id is resolved against the in-memory store (15-minute TTL), the submission is parsed, and the modal is closed with `response_action: clear` on success or `response_action: errors` on visible failure. The context is consumed only once a submission commits, so a visible error can be corrected and resubmitted in the same modal. With `--fail-first-submission` one submission is forced onto the error path, proving a failure returns a visible error rather than a success acknowledgement.
6. Finishes when all four capture combinations ({public, private} x {root, thread reply}) and both rejections are covered, or on Ctrl-C. A combination counts only once its modal opened *and* its submission committed: a failed `views.open`, an abandoned modal, or a duplicate of an already-captured message proves nothing. The run prints what is still outstanding as it changes.

The sanitised result is written to `.cache/slack-shortcut-result.json`. It contains the team id, granted scopes, per-capture timings (`ack_ms`, `views_open_ms`, `skew_s` — Slack wall-clock skew against the `X-Slack-Request-Timestamp`), which modal blocks were verified, whether each submission committed, and the rejection reasons. It never contains message text, actor ids, tokens, signing secrets, trigger ids, or raw payloads. Live results belong in the Milestone A evidence work for issue #8, separate from mocked test results.

## Expected observations to record

- Observed `ack_ms` and `views_open_ms` against Slack's three-second acknowledgement deadline, and how much headroom is lost through the cloudflared tunnel. If `ack_ms` is marginal, record the number as a Milestone A finding for issue #8 rather than tuning around it; measuring it is the point of this check.
- Whether the `message` object on a thread reply carries `thread_ts`, and whether Slack sets `thread_ts` on root messages (it should not).
- The exact `channel` shape for a DM interaction payload: the channel id prefix (`D...`) and the channel `name` Slack supplies.
- Whether Slack retries an interaction that responds slowly, and which headers distinguish a retry (`X-Slack-Retry-Num`, `X-Slack-Retry-Reason`, if present).
- The `x-oauth-scopes` header value actually granted by `auth.test` versus the five scopes requested on the app configuration page.
