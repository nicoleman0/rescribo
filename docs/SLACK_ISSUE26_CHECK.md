# Slack issue #26 feasibility check

This check covers the Slack provider boundaries needed for account linking,
channel policy, permalink retry, delayed follow-up delivery, and connection
lifecycle handling. The Python tests use fake provider responses. They are not
live Slack evidence.

## Provider contract

- `LinkCodeStore` creates a short-lived code and consumes it once. Redemption
  binds the code to the product workspace, signed Slack team, and signed Slack
  actor. Display names and email addresses are not used.
- `build_capture_modal(..., link_required=True)` adds the product-code field to
  the first capture modal. The submission parser keeps that code separate from
  report fields; the handler redeems it through `redeem_for_shortcut` using the
  signed shortcut team and actor.
- `ChannelEligibilityCache.validate_for_modal_start` may use a short-lived
  cache. `validate_for_submission` always calls `conversations.info` again.
  Archived, direct, group-direct, externally shared, and bot-unjoined
  conversations fail closed.
- A captured report remains present when `chat.getPermalink` fails. Retrying
  the same report can attach the link later.
- Follow-ups call `conversations.open` and then `chat.postMessage`. They do not
  use a temporary response URL, so the provider boundary has no 30-minute
  response-URL limit.
- Product membership is checked before both external writes. A revoked Slack
  credential disables the connection when Slack reports `token_revoked`,
  `invalid_auth`, `not_authed`, or `account_inactive`.
- A verified `app_uninstalled` event disables the connection and clears pending
  sends only when its team ID matches the connection.

The manifest keeps the five bot scopes from issue #3 and subscribes to the
`app_uninstalled` lifecycle event. It does not add user-token or message
history scopes.

## Deterministic checks

```sh
uv run pytest backend/tests/test_slack_issue26_boundaries.py
```

These tests prove the data and failure boundaries. They do not prove a signed
Slack modal was opened by a real user.

## Live API check

The existing issue #3 scope check must pass before changing the app. The
terminal check below repeats that assertion and calls `conversations.info` for
the two approved channel IDs:

```sh
task slack-issue26-check -- \
  --public-channel C... \
  --private-channel G...
```

An optional permalink check calls `chat.getPermalink` for a message timestamp
already known to the operator:

```sh
task slack-issue26-check -- \
  --public-channel C... \
  --private-channel G... \
  --message-channel C... \
  --message-ts 1758400000.000100
```

The delayed-DM check is an explicit external write. The supplied capture time
must be more than 30 minutes old. The message is fixed feasibility text and
contains no customer data:

```sh
task slack-issue26-check -- \
  --public-channel C... \
  --private-channel G... \
  --actor-id U... \
  --captured-at 2026-09-21T10:00:00Z \
  --send-delayed-dm
```

The result is written to `.cache/slack-issue26-result.json`. It records API
outcomes, IDs needed to correlate the test, and the returned message timestamp.
It does not record tokens, signing secrets, message text, or raw payloads.

## Evidence boundary and remaining action

The live API check cannot prove the account-linking acceptance criterion by
itself. That criterion needs one real product login to generate a code, one
signed Slack modal submission by the linked actor, and a second use rejected.
The current repository has no product login or Slack interaction endpoint, so
the identity and modal sequence remains deterministic harness evidence until
that product path exists.

The `app_uninstalled` parser and guard are covered by tests. Slack documents
that `apps.uninstall` requires an app client ID, client secret, and token, and
can return `no_permission` for a granular bot. `auth.revoke` revokes one token
and is not an app-uninstall test. A genuine uninstall claim therefore requires
the final Slack app-management action or a token with permission to call
`apps.uninstall`; neither is performed by the default script.

Sources:

- [Slack OAuth installation](https://docs.slack.dev/authentication/installing-with-oauth/)
- [`apps.uninstall`](https://docs.slack.dev/reference/methods/apps.uninstall/)
- [`auth.revoke`](https://docs.slack.dev/reference/methods/auth.revoke/)
- [`app_uninstalled` event](https://docs.slack.dev/reference/events/app_uninstalled/)
- [`conversations.info`](https://docs.slack.dev/reference/methods/conversations.info/)
- [`chat.getPermalink`](https://docs.slack.dev/reference/methods/chat.getPermalink/)
- [`conversations.open`](https://docs.slack.dev/reference/methods/conversations.open/)
- [`chat.postMessage`](https://docs.slack.dev/reference/methods/chat.postMessage/)
