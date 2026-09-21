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

## Test conditions

All runs used disposable resources, never production credentials or customer
data.

- **Slack**: app created from
  [`slack-feasibility-app-manifest.json`](slack-feasibility-app-manifest.json)
  into the disposable `feasibility-a` workspace (`T…`). The checks assert the
  granted bot scopes match the manifest's five exactly. Interactivity, the
  Messages tab, and the `submit_customer_feedback` message shortcut were
  enabled. The manifest had no event subscriptions during the shortcut run;
  #33 later added `app_uninstalled`. Whether the live app was updated with
  that subscription was not recorded, and neither check serves an events
  endpoint. Secrets live in the gitignored `.env.slack-feasibility`; the
  Request URL points at a cloudflared quick tunnel rewritten per run.
- **GitHub**: disposable GitHub App with **Issues: Read and write** and **Metadata:
  Read-only** only. The installation check ran with the private repository
  `nicoleman0/rescribo-integration-test` as the only selected repository; the
  lifecycle check also selected a second disposable anchor repository (see
  provider limitations). Webhook deliveries to a run-fresh smee.io channel;
  all `X-Hub-Signature-256` values verified on arrival. Secrets live in the
  gitignored `.env.github-feasibility`.
- Runs are dated 2026-09-20/21; sanitised results were reviewed from
  `.cache/{slack-shortcut,slack-issue26,github-installation,github-issue-lifecycle}-result.json`.

## App settings and granted scopes

| Check | Granted scopes / permissions | Also exercised |
| --- | --- | --- |
| Slack shortcut | `commands`, `channels:read`, `groups:read`, `chat:write`, `im:write` (exact match asserted) | Interactivity, message shortcut, Messages tab |
| Slack #26 | same five, re-asserted with `auth.test` | `conversations.info` on both approved channels, `chat.getPermalink` |
| GitHub installation | `issues: write`, `metadata: read` (selected repo only, private) | user-access verification through GitHub's authorisation flow |
| GitHub lifecycle | same, token restricted to the installed repository | smee webhook delivery, pull request and cross-repository rejection probes (both rejected) |

## Sanitised payload shapes by verified flow

Field lists only; values replaced with placeholders. Message text was never
recorded.

### Slack message shortcut (`message_action` interaction, post body form-encoded)

`payload.type=message_action`, `payload.team.id` (`T…`), `payload.user.id`
(`U…`), `payload.channel.id` (`C…` or `D…`), `payload.channel.name`,
`payload.trigger_id`, `payload.message_ts`, `payload.message.text`. On a
thread reply `payload.message.thread_ts` is present and differs from
`payload.message.ts`. Captures classed as root had `thread_ts` absent or equal
to `ts`; the result records only the classification. Slack gives a thread
parent a `thread_ts` equal to its own `ts`
([retrieving messages](https://docs.slack.dev/messaging/retrieving-messages/)).

### Rejection shapes

The DM's channel id is `D…`-prefixed and Slack supplied `channel.name`
`"directmessage"`. For the unapproved channel Slack supplied the channel's own
name (`not-approved`, chosen by the operator for the test workspace). Each
rejection entry keeps only the reason, channel id, channel name, and
`text_retained: false`; the message text was dropped.

### Capture modal lifecycle

`views.open` was called with the shortcut's `trigger_id` before the
acknowledgement was sent. An opaque context id, carried in the view's
`private_metadata`, bound the submission to the shortcut and was consumed only
when a submission committed. A forced failure answered `response_action:
errors` and left the context in place, so the same modal was corrected and
resubmitted; success answered `response_action: clear`.

The result lists five captures for four combinations. The public thread-reply
capture appears twice; the repeat is recorded as `duplicate: true`,
`submission_committed: false` and excluded from coverage.

### Slack scope header

`auth.test` returns the granted bot scopes in the `x-oauth-scopes` response
header. The live header is **comma-separated** (`commands,chat:write,...`);
whitespace-only splitting mis-parses it. The scripts now split on commas and
trim whitespace.

### Slack channel revalidation (`conversations.info`)

`channel.id`, `channel.is_private`, `channel.is_archived`, `channel.is_member`,
`channel.is_ext_shared`, `channel.is_im`, `channel.is_mpim`. Both approved
channels were eligible, and `is_private` matched the declared public and
private channels. The result keeps only channel id, eligibility, and kind.

### Slack permalink (`chat.getPermalink`)

Called with the public channel id and a known message timestamp; the response
carried a non-empty `permalink`. The result records only that a timestamp was
supplied and the link resolved, not the link itself.

### GitHub issue creation/read via installation token

Repository-restricted installation token with a one-hour expiry
(`token_expires_at` one hour after the created issue's `updated_at`).
`POST /issues` created issue #9 and a read-back returned matching number,
state `open`, `state_reason` `null`, and a round-tripped title; `updated_at`
timestamps preserved.

### GitHub webhook deliveries

Signed deliveries arrived in this order with no retries or duplicates:
`issues` `opened`, `issues` `closed`, `issues` `reopened`,
`installation_repositories` `removed`, `installation` `deleted`. The issues
payloads supplied `number`, `repository` full name, `action`, `state_reason`
(`completed` on REST close without an explicit reason, `reopened` on reopen),
and `updated_at`; the consumers refetched state from the API and compared
`updated_at`, so the payload body was never trusted for state. The
`installation_repositories` removal payload listed the removed repository in
`repositories_removed`. The parser does not read repositories from the
`installation` deletion payload, so the result does not show what it carried.

### Access-loss status codes

- After repository removal, reading the issue with the existing installation
  token returned HTTP 404 and was recorded as access-lost.
- After installation deletion, creating an installation token returned HTTP
  404 and was recorded as access-lost.

## Timings

`ack_ms` spanned 270–330 and `views_open_ms` 269–328. Both are measured
inside the receiver: `ack_ms` from reading the request body to writing the
response, and `views_open_ms` for the outbound `views.open` call, which takes
almost all of it. Handler time is about a tenth of Slack's 3-second
acknowledgement deadline. Transit through the cloudflared quick tunnel was not
measured.

## Provider limitations and test conditions

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

- Account linking has not been exercised live. It needs a product login to
  issue a code, a signed modal submission from the linked Slack actor, and a
  rejected second use. The repository has no product login or Slack
  interaction endpoint yet, so linking rests on deterministic tests
  ([`SLACK_ISSUE26_CHECK.md`](SLACK_ISSUE26_CHECK.md)).
- The bot DM sent more than 30 minutes after capture (issue #26's last
  acceptance item) has not been exercised live: the recorded result has
  `delayed_dm: null`, so `conversations.open` → `chat.postMessage` delivery
  and delayed-DM behaviour rest on deterministic harness evidence until that
  optional external write is run.
- Channel revalidation was exercised live only for the two eligible channels.
  The fail-closed cases (archived, direct, group-direct, externally shared,
  bot not a member) rest on deterministic tests.
- Whether Slack retries a slow interaction was not tested: every
  acknowledgement took under 330 ms, so `observed_retries: []` says nothing
  about it. Slack's interactivity docs say only that the user sees an error
  when the 3-second deadline is missed
  ([handling user interaction](https://docs.slack.dev/interactivity/handling-user-interaction/)).
- No Slack API error response was deliberately triggered live.
