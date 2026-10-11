# Tasks

Delivers #148. Paths are from the repository root. Decisions D1 to D7 are in `design.md`.

Do not call Slack. Do not edit `backend/connections/slack_identity.py`, `slack_inbound.py`, `backend/integrations/slack/modals.py`, `shortcuts.py`, or `docs/slack-app-manifest.json` (#149). Do not change `client.eligible_channel`. Rebase on `main` after #146 merges, before group 5.

Tasks marked [shared] touch a file the brief does not give this issue. Do them only if the coordinator's answer file approves them. Otherwise use the fallback named in the task.

Write each group's tests first and see them fail.

## 1. Policy and Slack client

- [x] 1.1 `backend/tests/test_slack_channel_policy.py`: `unavailable_reason` returns `direct_message`, `group_direct_message`, `externally_shared`, and `archived` for each flag, in that order of precedence, and `None` for an internal channel with no `is_member` key. The existing `validate_channel` tests still pass unchanged.
- [x] 1.2 `backend/integrations/slack/policy.py`: add `unavailable_reason(channel: SlackChannel) -> str | None` and make `validate_channel` use it before its membership check (D1). No behaviour change to `validate_channel`.
- [x] 1.3 `backend/tests/test_settings_providers.py`, with `integrations.slack.client.decrypt` and `WebClient` patched as the existing channel test does:
  - `member_channels` calls `users_conversations` with `types="public_channel,private_channel"`, `exclude_archived=True`, `limit=200`, follows `next_cursor` across two pages, and stops when it is empty;
  - it stops at 1,000 channels and reports that more remained;
  - `channel_options` sorts eligible channels and Slack Connect channels by name, marks the latter `externally_shared`, drops archived channels, DMs, and group DMs, and carries `truncated`;
  - a `SlackApiError` whose response has `status_code == 429` becomes `SetupError` with code `slack_rate_limited`;
  - with `RESCRIBO_SLACK_FAKE_DELIVERY=True`, `channel_options("fake")` returns the three fake channels without decrypting, `channel_details("fake", "C0E2EPUBLIC")` passes, `channel_details("fake", "C0E2ESHARED")` raises `ChannelRejected`, and an unknown ID raises `SlackApiError`.
- [x] 1.4 New `backend/integrations/slack/fake_channels.py` with `FakeDirectoryClient` (D7).
- [x] 1.5 New `backend/integrations/slack/channel_directory.py`: Django-free `PAGE_SIZE`, `MAX_LISTED_CHANNELS`, and `collect_member_channels`. `client.py` imports the shared pagination function and constants; `scripts/list_slack_channels.py` imports from the Django-free module (D2).
- [x] 1.6 `backend/integrations/slack/settings.py`: add `channel_options`; `channel_details` calls `client.channel_info` (D2). The existing `test_channel_policy_rejects_ineligible_sources` must pass unchanged.
- [x] 1.7 [shared] `backend/connections/providers.py`: re-export `channel_options`. Fallback: none; ask if refused.
- [x] 1.8 `backend/tests/test_slack_channel_script.py`: run the feasibility script in a subprocess without a Slack token or Django settings and assert it exits with the missing-token message before any API call.

## 2. Service and endpoint

- [x] 2.1 `backend/tests/test_settings.py`:
  - owner `GET channels/` with `connections.providers.channel_options` patched returns 200 with `channels` and `truncated`;
  - a member gets 403 and a user of another workspace gets the same answer the existing foreign-workspace test expects, and `channel_options` is not called in either case;
  - separate disconnected and errored Slack connection rows answer 400 `not_connected` without calling `channel_options`;
  - `channel_options` raising `SetupError("slack_rate_limited", ...)` answers 400 with that reason, and raising `SlackApiError` answers 400 `provider_unavailable`;
  - no `AllowedChannel` row changes on any of these;
  - submit-time check: `POST channels/` with an ID the list never held still goes through `channel_details`, and a `ChannelRejected` answers 400 `channel_ineligible` with no row written.
- [x] 2.2 `backend/tests/test_demo.py`: add `services.list_channels(owner)` to the actions refused with `demo_workspace`.
- [x] 2.3 `backend/connections/services.py`: `list_channels(actor)` (D4).
- [x] 2.4 `backend/connections/views.py`: `ChannelOptionSerializer`, `ChannelOptionsSerializer`, and `ChannelView.get` with `extend_schema(responses={200: ..., 400: ErrorSerializer})` (D5). The view calls `translated` and maps provider errors with `providers.safe_provider_error`, as `post` does. Keep it thin.
- [x] 2.5 Run `task schema` and commit `frontend/openapi.yaml` and `frontend/src/api/schema.d.ts`.

## 3. Frontend

- [x] 3.1 `frontend/src/features/settings/settings-page.test.tsx`, as owner with the active Slack connection, stubbing `GET ${base}channels/`:
  - the select offers `#key-accounts · Private` and `#support-requests · Public`, the Slack Connect option is disabled and names the reason, and an already allowed channel is not offered;
  - an unavailable option with an unrecognized reason is disabled and displays `Not allowed`;
  - "Allow channel" is disabled until a channel is chosen and the box in the channel form is ticked; ticking the connect form's box does not enable it;
  - submitting posts `{ version, channel_id, consent: true }` through a successful POST response, and afterwards the box is unticked;
  - no textbox named "Slack channel ID" exists;
  - while the list is pending, a status named "Loading Slack channels" shows;
  - a 400 with `slack_rate_limited` shows its detail and "Try again", and pressing it refetches;
  - an empty list shows the invite text and "Refresh channel list";
  - `truncated: true` shows "Showing the first 1,000 channels.";
  - the section's heading comes before the "Reconnect Slack" button in document order;
  - as a member, and with `demo` true, `GET channels/` is never requested.
  Update "channel actions never read as a check result" only as far as the new stub requires.
- [x] 3.2 [shared] `frontend/src/api/settings.ts`: `SlackChannelOptions` type from the schema and `getSlackChannels`. Fallback: put both in `allowed-channels.tsx`.
- [x] 3.3 New `frontend/src/features/settings/allowed-channels.tsx` (D6). Move the section out of `connection-settings.tsx` first with no behaviour change and run the tests, then build the picker. Two commits if the implementer commits in steps.
- [x] 3.4 `connection-settings.tsx`: render `AllowedChannels` after the facts and job counts and before the connect form. Remove the `channel` state. Keep `consent` for the connect form only.
- [x] 3.5 Read `frontend/DESIGN.md` first. Every control keeps the 44 px phone minimum. No new colours or loading pattern.

## 4. E2E

- [x] 4.1 `frontend/e2e/settings.spec.ts`, one test, not mocked (the fake channels answer under `RESCRIBO_SLACK_FAKE_DELIVERY`): sign in as an owner the other settings tests do not use for channel state, choose `#support-requests`, tick the box, press "Allow channel", see it under allowed channels, then remove it so a rerun starts clean. At a 390 px viewport assert no horizontal overflow and that `axeViolations(page)` is empty.

## 5. Screenshots and checks

- [x] 5.1 After screenshots: reseed with `seed_demo` and `seed_test_accounts --json`, start the dev servers on 8148 and 5148, then run `SHOTS_BASE=http://127.0.0.1:5148 node .claude/skills/work-issues/scripts/shots.mjs .claude/shots/after` and `SHOTS_BASE=http://127.0.0.1:5148 node .claude/skills/work-issues/scripts/owner-shots.mjs .claude/shots/after`. The demo visitor is a member, so only the `settings-owner-*` shots show this change. Include desktop and phone shots in light and dark themes in the comparison page. Stop the servers.
- [x] 5.2 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 5.3 `task check test build schema-check` passes with PostgreSQL and Redis running.
- [x] 5.4 `RESCRIBO_E2E_API_PORT=8148 RESCRIBO_E2E_FRONTEND_PORT=5148 task e2e` passes.
- [x] 5.5 PR body: list checks 3 to 7 from `design.md` under "Decisions to review" as not verified live. State that mocked tests cover the full `users.conversations` behavior and record the coordinator's live feasibility check for the method, scopes, and public/private response.

## Workflow follow-up

- Archive the change in the PR that completes it.
