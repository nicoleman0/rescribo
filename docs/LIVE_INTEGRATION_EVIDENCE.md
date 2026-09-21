# Live integration evidence (Milestone A)

Sanitised evidence consolidates the four opt-in live feasibility checks: Slack
shortcut capture (issue #3), Slack identity and delivery boundaries (issue
#26), GitHub App installation (issue #1), and the GitHub issue lifecycle
(issue #2). The underlying runs are described in
[`SLACK_SHORTCUT_CHECK.md`](SLACK_SHORTCUT_CHECK.md),
[`SLACK_ISSUE26_CHECK.md`](SLACK_ISSUE26_CHECK.md),
[`GITHUB_INSTALLATION_CHECK.md`](GITHUB_INSTALLATION_CHECK.md), and
[`GITHUB_ISSUE_LIFECYCLE_CHECK.md`](GITHUB_ISSUE_LIFECYCLE_CHECK.md).

This document is the live record. The deterministic pytest suites under
`backend/tests/` are mocked provider evidence and remain separate from it;
nothing in this document was produced by a mocked test.

## Test conditions and app settings

All runs used disposable resources, never production credentials or customer
data.

- **Slack**: app created from
  [`slack-feasibility-app-manifest.json`](slack-feasibility-app-manifest.json)
  into the disposable `feasibility-a` workspace (`T0C3DSXLYHG`). Bot scopes
  requested were exactly `commands`, `channels:read`, `groups:read`,
  `chat:write`, `im:write`; the check asserts the granted set matches exactly.
  Interactivity and the `submit_customer_feedback` message shortcut were
  enabled, and only the `app_uninstalled` bot event was subscribed. Secrets
  live in the gitignored `.env.slack-feasibility`; the Request URL points at a
  cloudflared quick tunnel rewritten per run.
- **GitHub**: disposable GitHub App with **Issues: Read and write** and **Metadata:
  Read-only** only, installed on the private repository
  `nicoleman0/rescribo-integration-test`. Webhook deliveries to a run-fresh
  smee.io channel; all `X-Hub-Signature-256` values verified on arrival.
  Secrets live in the gitignored `.env.github-feasibility`.
- Runs are dated 2026-09-20/21; sanitised results were reviewed from
  `.cache/{slack-shortcut,slack-issue26,github-installation,github-issue-lifecycle}-result.json`.

## Test (app) settings and granted scopes

| Check | Granted scopes / permissions | Additional settings exercised |
| --- | --- | --- |
| Slack shortcut | `commands`, `channels:read`, `groups:read`, `chat:write`, `im:write` (exact match asserted) | Interactivity, message shortcut, Messages tab |
| Slack #26 | same five, `auth.test` re-asserted | `app_uninstalled` event subscription; manifest unchanged |
| GitHub installation | `issues: write`, `metadata: read` (selected repo only, private) | user-access verification through GitHub's authorisation flow |
| GitHub lifecycle | same, token restricted to the installed repository | smee webhook delivery, optional PR/cross-repo rejection probes |

## Sanitised payload shapes by verified flow

Field lists only; values replaced with placeholders. Message text was never
recorded.

### Slack message shortcut (`message_action` interaction, post body form-encoded)

`payload.type=message_action`, `payload.team.id` (`T…`), `payload.user.id`
(`U…`), `payload.channel.id` (`C…` or `D…`), `payload.channel.name`,
`payload.trigger_id`, `payload.message_ts`, `payload.message.text`. On a
thread reply `payload.message.thread_ts` is present and points at the parent;
root messages carry no `thread_ts`.

### DM rejection shape

The channel id is `D…`-prefixed and Slack supplies `channel.name`
`"directmessage"`. An unapproved public channel supplies `channel.name`
`"not-approved"`. In both rejections the message text was dropped and recorded
only as `text_retained: false`; no other channel metadata is retained.

### Capture modal lifecycle

`views.open` called with the shortcut's `trigger_id` inside the acknowledgement
window; the context id and view id carried the modal and were consumed once on
`view_submission`. A forced failure answered `response_action: errors` and the
same modal allowed correction and resubmission; success answered
`response_action: clear`.

### Slack scope header

`auth.test` returns the granted bot scopes in the `x-oauth-scopes` response
header. The live header is **comma-separated** (`commands,chat:write,...`);
whitespace-only splitting mis-parses it. The scripts now split on both.

### GitHub issue creation/read via installation token

Repository-restricted installation token (one-hour expiry, observed
`token_expires_at` exactly one hour after mint). `POST /issues` created issue
#9 and a read-back returned matching number, state `open`, `state_reason`
`null`, and a round-tripped title; `updated_at` timestamps preserved.

### GitHub webhook deliveries

Signed deliveries arrived in this order with no retries or duplicates:
`issues` `opened`, `issues` `closed`, `issues` `reopened`,
`installation_repositories` `removed`, `installation` `deleted`. The issues
payloads supplied `number`, `repository` full name, `action`, `state_reason`
(`completed` on REST close without an explicit reason, `reopened` on reopen),
and `updated_at`; the consumers refetched state from the API and compared
`updated_at`, so the payload body was never trusted for state. The
`installation_repositories` removal payload listed the removed repository
name; the `installation` deletion payload carried no repositories.

### Access-loss status codes

- After repository removal, reading the issue with the existing installation
  token returned HTTP 404 and was recorded as access-lost.
- After installation deletion, creating an installation token returned HTTP
  404 and was recorded as access-lost.

## Timings

Through the cloudflared quick tunnel, `ack_ms` spanned 270–330 and
`views_open_ms` 269–328 — about a tenth of Slack's 3-second acknowledgement
deadline. Tunnel latency leaves ample headroom; re-measuring per configuration
change is unnecessary unless the handler changes.

## Provider limitations and test conditions

- Slack retries interactions not answered within three seconds; the receiver
  is therefore threaded. No retries were observed during the run
  (`observed_retries: []`).
- GitHub Apps automatically receive `installation` and
  `installation_repositories` events; only the *Issues* event needed a manual
  subscription.
- GitHub no longer accepts a GitHub App user token for changing installation
  repository selection, and it will not remove a repository that is the last
  one selected. The lifecycle check therefore keeps a second disposable anchor
  repository, waits for browser-driven removal, and records both
  post-removal status codes.
- Slack uninstalls could not be genuinely exercised: `apps.uninstall` needs the
  app client id/secret plus a token and may return `no_permission` for a
  granular bot; `auth.revoke` revokes one token and is not an uninstall. The
  `app_uninstalled` parser is covered by deterministic tests only.
- `x-oauth-scopes` is comma-separated, which the mocked tests did not cover;
  the scope comparison now lives once in `scripts/slack_live.py`.

## Known gaps in live coverage

- The bot DM sent more than 30 minutes after capture (issue #26's last
  acceptance item) has not been exercised live: the recorded result has
  `delayed_dm: null`, so `conversations.open` → `chat.postMessage` delivery
  and delayed-DM behaviour rest on deterministic harness evidence until that
  optional external write is run.
- Genuine HTTP failure responses for the live Slack calls beyond the ones
  above were not deliberately triggered.
