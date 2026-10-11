# Design

## Context

- `ChannelView.post` (`backend/connections/views.py`) takes `channel_id`, `version`, `consent`, and `remove`. `channel_id` must match `^[CG][A-Z0-9]+$`. Links are not accepted, although the spec says "by ID or link".
- `services.update_channel` locks the connection, then calls `providers.channel_details`, which is `integrations/slack/settings.py::channel_details`: `conversations.info` followed by `policy.validate_channel`. A `ChannelRejected` becomes a 400 with reason `channel_ineligible`.
- `client.eligible_channel` is the capture path's check. This change does not touch it.
- The Slack card (`connection-settings.tsx`) holds one `consent` state. Both the connect form and the channel form read it. It is `useState`, so it resets on the full page load after the Slack redirect.
- The e2e workspace has an active Slack connection with the credential `"fake"`, and the demo workspace has `"demo-not-a-credential"`. Neither decrypts. `decrypt` raises `SetupError("credential_unavailable")`.
- The demo visitor is a member, and the demo owner has no password. No one reaches owner controls in the demo through the UI. `refuse_demo` guards the services.
- `slack_sdk.WebClient` does not retry on HTTP 429 unless a rate-limit handler is added. A 429 raises `SlackApiError` with `response.status_code == 429`.

## Slack method

Decision: `users.conversations` with `types=public_channel,private_channel`, `exclude_archived=true`, `limit=200`.

| | `users.conversations` | `conversations.list` |
| --- | --- | --- |
| Returns | only conversations the bot is in | every public channel, plus private ones the bot is in |
| Rate limit | Tier 3, "50+ per minute" | Tier 2, "20+ per minute" |
| `is_member` | absent: "We omit the `is_member` and `num_members` fields in this method's response." | present |
| Proven live with our scopes | yes, 11 Oct 2026 | yes, `task slack-channels` |

Sources: <https://docs.slack.dev/reference/methods/users.conversations> and <https://docs.slack.dev/reference/methods/conversations.list>, read on 2026-10-11. Both pages list `channels:read` and `groups:read` for bot tokens.

Why: the cost of `conversations.list` grows with the size of the Slack workspace. A workspace with 5,000 public channels needs 25 pages at Tier 2 to find the three the bot is in, and its pages can come back short because "Fewer than the requested number of items may be returned, even if the end of the list hasn't been reached". The cost of `users.conversations` grows with the bot's own memberships, which an owner creates one invite at a time.

Live check on 11 Oct 2026 used the feasibility bot token and the five granted scopes. One read-only `users.conversations` call returned `ok: true`, no missing scope, and a public and private channel the bot is in. Rows included `is_private`, `is_ext_shared`, and `is_archived`, but no `is_member`; the cursor was empty. The live call used `types=public_channel,private_channel`, `exclude_archived=true`, and `limit=200`.

The maintainer still needs to verify before merge: a public channel the bot is not in stays out; a Slack Connect channel appears unavailable; both public and private channels can be allowed; removal of the bot before submit is rejected; and pagination across more than 200 memberships works live. Mocked tests cover pagination and submit-time changes. Do not call Slack from implementation checks.

## Decisions

### D1. One home for the eligibility rules
`policy.py` gains `unavailable_reason(channel: SlackChannel) -> str | None`. It returns the first of `direct_message`, `group_direct_message`, `externally_shared`, `archived`, or `None`. `validate_channel` calls it and then checks membership. The list uses it without the membership check, because `users.conversations` omits `is_member` and returns only the bot's conversations.

### D2. Provider calls stay in `integrations/slack/`
- `channel_directory.py` has no Django or connection imports. It owns `PAGE_SIZE`, `MAX_LISTED_CHANNELS`, and `collect_member_channels(client)`, which follows `response_metadata.next_cursor` for at most five pages and returns the raw channel dicts with a truncated flag. The app client and `scripts/list_slack_channels.py` both use it.
- `client.member_channels(credential) -> list[dict]` passes the directory client to `collect_member_channels`.
- `client.channel_info(credential, channel_id) -> dict`: `conversations.info`, the call `channel_details` makes today.
- Both go through `_directory_client(credential)`, which returns the fake under `RESCRIBO_SLACK_FAKE_DELIVERY`, the same switch `_delivery_client` uses.
- `settings.channel_options(credential) -> dict`: returns eligible channels and Slack Connect channels, mapped to `channel_id`, `name`, `is_private`, and `unavailable_reason` (empty when it can be chosen), sorted by name, with `truncated`. It omits rows whose reason is not `externally_shared`, including archived channels, DMs, and group DMs. It turns a 429 into `SetupError("slack_rate_limited", "Slack asked us to wait. Try again in a minute.")`.
- `settings.channel_details` calls `client.channel_info` and is otherwise unchanged.

### D3. Rate limits and large lists
- No sleep and no retry inside the web request. A 429 becomes a 400 with reason `slack_rate_limited`, and the owner retries.
- Worst case is five Slack calls per list request, with the 10 second client timeout each.
- Past 1,000 memberships the response has `truncated: true`, and the UI says the list is cut short. A bot in more than 1,000 channels is not a case this product expects.
- No server cache. The browser caches the list for 30 seconds (D6).
- Alternative: a Celery task that syncs channels into a table. Rejected: a table, a task, and a staleness rule for a list that is read a few times per workspace.

### D4. Listing does not lock or version
`services.list_channels(actor)` calls `refuse_demo`, reads the Slack connection for the workspace, requires `status == active` (else `SetupError("not_connected")`), and calls `providers.channel_options` outside any transaction. A read needs no row lock, and a slow Slack call must not hold one. `OwnerWorkspaceView` already enforces owner and workspace.

### D5. API
`GET /api/workspaces/{workspace_id}/channels/` on the existing `ChannelView` and route.

```json
{
  "channels": [
    {"channel_id": "C0E2EPUBLIC", "name": "support-requests", "is_private": false, "unavailable_reason": ""},
    {"channel_id": "C0E2ESHARED", "name": "partner-shared", "is_private": false, "unavailable_reason": "externally_shared"}
  ],
  "truncated": false
}
```

Errors use the existing `ErrorSerializer` shape through `translated`: 400 with `not_connected`, `demo_workspace`, `slack_rate_limited`, `credential_unavailable`, `missing_scopes`, or `provider_unavailable`. The `POST` is unchanged.

### D6. Frontend
- New `allowed-channels.tsx` in `features/settings` holds the whole "Allowed Slack channels" section: heading, help text, allowed list with Remove, and the form. `connection-settings.tsx` passes `workspaceId`, `workspaceName`, `connection`, `action`, and `busy`. The "Connection update failed" box renders within this section on `action.error`.
- The list is a `useQuery` with key `['slack-channels', workspaceId]`, `staleTime` 30 seconds, enabled only for an owner with an active Slack connection outside the demo. The key sits outside `settingsKey`, so unrelated settings actions do not call Slack. Refetch on window focus stays on: an owner who invites the bot in Slack and comes back sees the channel.
- The control is `SelectField` (the shared `NativeSelect`). Options read `#name · Public` or `#name · Private`. Unavailable options are `disabled` and read `#name · Slack Connect, not allowed`; an unknown unavailable reason reads `Not allowed`. Channels already in `connection.channels` are filtered out. A native select has type-ahead and needs no new component.
  - Alternative: a filter box with a result list. Rejected for now: a new pattern for a list that is short in practice.
- States, composed from the shared components per the "Async state pattern" in `frontend/DESIGN.md`:
  - loading: `LoadingState` with the label "Loading Slack channels";
  - error: `ErrorState` with the server's `detail` and the shared `RetryButton`;
  - empty (no channel left to choose): "The app is not in any other channel. In Slack, invite it to a channel, then load the list again." with a "Refresh channel list" button;
  - ready: the select, the confirmation box, "Allow channel", and a "Refresh channel list" outline button;
  - `truncated`: one muted line, "Showing the first 1,000 channels."
- The form has its own `channelConsent` state and checkbox labelled "Reports captured from this channel will be visible to all members of {workspace}." It submits the current checkbox value and resets after a channel is allowed, so each channel is confirmed. The connect and reconnect form keeps its existing consent box and wording.
- A shared `Separator` visually divides the allowed-channels section from Reconnect, Check status, and Disconnect actions. The section renders after the facts and job counts and before those connection actions.
- The owner screenshot script `.claude/shots/owner-shots.mjs` (git-ignored, written by the planner) waits for the heading "Allowed Slack channels". Keep that heading.

### D7. Fakes
- New `backend/integrations/slack/fake_channels.py`: a `FakeDirectoryClient` with `users_conversations` and `conversations_info` over three fixed channels: `C0E2EPUBLIC` `support-requests` (public), `G0E2EPRIVATE` `key-accounts` (private), `C0E2ESHARED` `partner-shared` (`is_ext_shared`). `conversations_info` adds `is_member: true` and raises `SlackApiError` `channel_not_found` for other IDs. The real policy runs on the fake data.
- Development and e2e run with the flag on, so the picker and the submit work with no Slack and no route stubs.
- Demo workspace: `refuse_demo` runs first in `list_channels`, and the query is disabled when `demo` is true. No Slack call, no fake list. The demo visitor is a member and never sees the section.
- With the flag off and a credential that does not decrypt, the section shows the error state.

## Shared files

Each needs the coordinator's yes. The tasks mark them.

- `backend/connections/providers.py`: one line, `from integrations.slack.settings import channel_options as channel_options`. Without it `services.py` would import the integration directly, against the file's "Provider boundary" rule.
- `frontend/src/api/settings.ts`: one type and one fetcher, `getSlackChannels`. If refused, they live in `allowed-channels.tsx`.
- `backend/integrations/slack/settings.py` and the new `fake_channels.py`: the brief names `client.py` and `policy.py`, but `channel_details` lives in `settings.py`.
- `scripts/list_slack_channels.py`: imports the Django-free pagination module and uses the same channel cap when it reports a truncated result. A subprocess test verifies that it reports a missing token before any Slack call without Django settings configured.

## Live checks before merge

None of these can run in CI. Mocked tests cover the same paths with canned responses.

1. Verified by the coordinator on 11 Oct 2026 with the feasibility bot token and five current scopes: `users.conversations` with `types=public_channel,private_channel` answered `ok`, not `missing_scope`.
2. Verified in that call: a public and private channel the bot is in appeared; the private channel carried `is_private: true`.
3. A public channel the bot is not in does not appear.
4. A Slack Connect channel the bot is in appears with `is_ext_shared: true` and shows as unavailable.
5. Picking a public and a private channel allows both.
6. Remove the bot from a listed channel without reloading, then submit it: the server rejects it.
7. Not checkable without a bot in more than 200 channels: live pagination. Mocked only.

Checks 3 to 7 remain for the maintainer before merge. Pagination beyond 200 is covered by mocked tests only. If check 1 fails, switch `client.member_channels` to `conversations.list` with an `is_member` filter and rerun.

## Questions

Q1 to Q4 were resolved in `.claude/answers/plan.md`: show Slack Connect as unavailable and omit archived channels; remove the raw ID field; use a second consent box in the channel form; place the section above the connection actions.

- Q1. Channels the bot is in that are not eligible. (a) Show Slack Connect channels as unavailable with the reason, leave archived out. (b) Leave all of them out. (c) Show both kinds as unavailable. Recommended: (a).
- Q2. The raw ID field. (a) Remove it. (b) Keep it behind an "Enter a channel ID instead" control. (c) Keep it visible under the list. Recommended: (a).
- Q3. The consent box. (a) A second box in the channel form with its own state. (b) One box, moved beside the channel form, with the connect form reading it from there. (c) Leave it and fix the hint. Recommended: (a).
- Q4. Where the section sits. (a) In the Slack card, above the connect, check, and disconnect actions. (b) Its own card under the Slack card. (c) Where it is. Recommended: (a).
