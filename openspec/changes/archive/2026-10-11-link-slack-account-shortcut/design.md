# Design

## Context

See `proposal.md` for the problem. What the code does today:

- `docs/slack-app-manifest.json` declares one shortcut, `submit_customer_feedback`, of type `message`.
- `SlackInteractionsView.post` dispatches on `payload["type"]`: `message_action` to `slack_inbound.start_capture`, every `view_submission` to `slack_inbound.submit_capture`, `block_actions` to the outcome handler. A payload of type `shortcut` falls through and gets an empty 200.
- `parse_message_shortcut` requires `channel` and `message`. A global shortcut carries neither.
- `start_capture` stores a `SlackCaptureContext` with `link_required=True` for an unlinked actor and adds a "Product linking code" field to the capture modal. `_submit_locked` redeems it with `slack_identity.redeem_link_code`, then goes on to save the report.
- `redeem_link_code(code, workspace_id, team_id, user_id)` holds every check: digest, workspace, active member, single use, expiry, and the unique Slack identity. It raises `LinkCodeRejected` with a sentence for the member.
- `slack-account.tsx` polls the identity every five seconds while a code is outstanding, so Settings picks up a link made in Slack with no change.

Slack facts, from Slack's docs:

- Scope: "To make shortcuts available in Slack, your app must have the `commands` permission scope." ([Implementing shortcuts](https://docs.slack.dev/interactivity/implementing-shortcuts/)). The app holds `commands`. No scope changes.
- Payload: a global shortcut's `type` "will return `shortcut`", a message shortcut's "will return `message_action`". `channel`, `message`, and `response_url` "will only be included for message shortcuts". The example global payload carries `team.id`, `user.id`, `callback_id`, and `trigger_id`. ([Shortcuts payload reference](https://docs.slack.dev/reference/interaction-payloads/shortcuts-interaction-payload/))
- Global shortcuts are "available to users via the shortcuts button in the message composer" and "when using search in Slack". They go to the same interactivity request URL, and the app must answer within 3000 ms.

## Goals / Non-Goals

**Goals:**
- A member links their Slack account from a shortcut that says what it does.
- The redeem rule keeps one home, `redeem_link_code`.
- The interactions view stays a thin router.

**Non-Goals:**
- Sign in with Slack, one-time links, or a slash command.
- A new scope, model, or migration.
- Changing who may link, how codes are issued, or the unlink flow.
- Removing the linking field from the capture modal.

## Decisions

1. **Global shortcut, callback id `link_rescribo_account`, name "Link Rescribo account".** The name is 21 characters, inside Slack's 24-character limit for shortcut names and modal titles. The callback id is a constant in `slack_inbound.py` beside `CAPTURE_CALLBACK_ID`, and the modal reuses it as its `callback_id`.

2. **Parse the global payload in `shortcuts.py`.** Add a frozen `GlobalShortcut` (`callback_id`, `team_id`, `actor_id`, `trigger_id`) and `parse_global_shortcut`, which requires `type == "shortcut"` and reuses `_require_string`. A malformed payload raises `ShortcutPayloadError`, which the view already turns into 400.

3. **No server-side context for the link modal.** The capture modal needs one because it holds message text and a channel. The link modal holds nothing. On submission the workspace comes from `active_connection(team.id)` and the actor from `user.id`, both from the signed payload. `private_metadata` stays empty. This is why there is no model change.

4. **`start_link(payload)` in `slack_inbound.py`.** Parse, return unless the callback id matches, return if the team has no active connection (as `start_capture` does), then:
   - linked to an active member: open `build_notice_modal("Already linked", ...)`;
   - otherwise: open `build_link_modal()`.
   One indexed read and one `views.open` with `INTERACTIVE_TIMEOUT`, so it fits the three-second window.

5. **`submit_link(payload)` in `slack_inbound.py`.** Read the code from the view state, read `team.id` and `user.id` from the payload, and resolve the connection. Then call `redeem_link_code`. It does not check the code itself.
   - Empty code: `response_action: errors` on `slack_link_code` with "Enter the linking code from Rescribo settings.", the sentence the capture modal already uses. Move it to one constant.
   - `LinkCodeRejected`: `response_action: errors` on `slack_link_code` with `str(rejected)`.
   - Success: `response_action: update` with `build_notice_modal("Account linked", ...)` naming the workspace.
   - No active connection at submit time: `response_action: update` with a notice that Slack is no longer connected.

6. **Route submissions by `view.callback_id`.** Add `submit_view(payload)` to `slack_inbound.py`: `link_rescribo_account` goes to `submit_link`, anything else to `submit_capture` as today. The view calls `submit_view` for `view_submission` and `start_link` for `shortcut`. The edit to `views.py` is confined to the dispatch `try` block in `SlackInteractionsView.post`: one changed call and one added branch. #148 edits `ChannelView` in the same file, about 180 lines above, so the rebase should be clean.

7. **`build_link_modal()` and `parse_link_submission()` in `modals.py`.** The modal has one section of help text ("Generate a code in Rescribo settings, under Your Slack account. Codes last 5 minutes.") and one input block. The block id is `slack_link_code` with action id `value`, the same as the capture modal's field, so `_input_value` reads both. The five-minute figure comes from `LINK_CODE_LIFETIME`, passed in by the caller, so the number has one home.

8. **Capture modal unchanged, text updated.** `UNLINKED_TEXT` becomes: "Your Slack account is not linked to Rescribo. Generate a code in Rescribo settings, then run the "Link Rescribo account" shortcut." The capture modal's field and its tests stay. This follows the maintainer decision to keep the capture field.

9. **Settings text.** The linked-off sentence becomes: 'Link your Slack account to capture reports from Slack. Generate a code, run the "Link Rescribo account" shortcut in Slack, and paste the code.' Nothing else in the component changes.

10. **Manifest.** Add a second entry to `features.shortcuts`: `{"name": "Link Rescribo account", "type": "global", "callback_id": "link_rescribo_account", "description": "Link your Slack user to your Rescribo account"}`. Scopes are untouched. `docs/slack-feasibility-app-manifest.json` belongs to the #3 feasibility check and stays as it is.

## Risks / Trade-offs

- [The live app keeps the old manifest until the maintainer updates it] → Until then the shortcut does not exist in Slack and Settings names a shortcut members cannot find. Update the manifest before or with the deploy. Steps below.
- [Two places take a linking code] → Both call `redeem_link_code`, and the block id and empty-code sentence are shared. The capture field stays by maintainer decision; removing it would force unlinked members to restart their capture.
- [A Slack user whose member was revoked cannot relink to another member] → `linked_membership` ignores the inactive member, so the code modal opens, and `redeem_link_code` then refuses with "This Slack account is already linked to another member." The capture modal behaves the same way today. This change keeps it and covers it with a scenario. Freeing the identity on revocation is a separate issue.
- [A team with no active connection gets no feedback] → The app has no token to open a view. `start_capture` has the same limit.
- [Before and after screenshots show no difference] → The demo member is already linked, so the changed sentence does not appear in these screenshots. The component test covers it.

## Migration Plan

Deploy order: code first or together with the manifest. The old manifest keeps working with the new code.

Manifest steps for the maintainer, on the live Slack app:

1. Open the app at api.slack.com/apps, **App Manifest**, and add the `link_rescribo_account` entry from `docs/slack-app-manifest.json` to `features.shortcuts`. Or call `apps.manifest.update` with the app ID and the edited manifest, as `docs/PROVIDER_SETUP.md` section 8 does for `apps.manifest.create`.
2. Save. Scopes do not change, so Slack should not ask for a reinstall. If it does, reinstall from Settings and note it in the PR.
3. Confirm **Interactivity & Shortcuts** lists both shortcuts and the request URL is unchanged.

Live checks for the PR, in the disposable workspace:

1. Unlinked member: search "Link Rescribo account" in Slack, run it, and see the code modal inside three seconds.
2. Submit with no code, then with a wrong code: the modal stays open with an error under the field.
3. Generate a code in Settings and submit it: the modal confirms, and Settings shows the linked user and team within five seconds.
4. Submit the same code again from a second Slack user: refused.
5. Run the shortcut again as the linked member: the "Already linked" notice.
6. Run "Submit customer feedback" as the linked member: no linking field, capture works.

`docs/LIVE_INTEGRATION_EVIDENCE.md` is not edited in this change. After the live run the maintainer would add a dated row for it and replace the first bullet under "Known gaps in live coverage" ("Account linking has not been exercised live...") with what was run.

Rollback: revert the commit. The shortcut then gets an empty 200 and does nothing. Remove it from the manifest.

## Decisions from review

1. The maintainer confirmed option 2 on 11 Oct 2026: a global shortcut, "Link Rescribo account", opens the code modal. It replaces the 10 Oct Sign in with Slack decision.
2. Keep the linking field in the capture modal. This lets an unlinked member finish a capture in one flow; removing it would force them to leave mid-capture, generate a code in Settings, then restart the shortcut.
3. An already linked member sees a notice with no code field.
4. No slash command. The global shortcut is the single dedicated entry point.
5. Leave ADR 0005 unchanged.
