# Tasks

Delivers #149. Read `design.md` first. Do not touch `backend/integrations/slack/client.py`, `policy.py`, `settings.py`, `backend/connections/services.py`, `ChannelView` in `views.py`, `connection-settings.tsx`, or `docs/LIVE_INTEGRATION_EVIDENCE.md` (#148 and the maintainer own them). Do not call Slack.

In each group, write the tests first and see them fail.

## 1. Payload and modal (integration module)

- [x] 1.1 In `backend/tests/test_slack_shortcut.py`, add tests for `parse_global_shortcut`: the example payload from Slack's reference parses to callback id, team, actor, and trigger; a `message_action` payload, a missing `team.id`, a missing `user.id`, and a missing `trigger_id` each raise `ShortcutPayloadError`. Verify: they fail on current code.
- [x] 1.2 Add `GlobalShortcut` and `parse_global_shortcut` to `backend/integrations/slack/shortcuts.py`, reusing `_require_string`. Update the module docstring to cover both shortcut kinds. Verify: 1.1 passes.
- [x] 1.3 In `test_slack_shortcut.py`, add tests: `build_link_modal` returns a modal titled "Link Rescribo account" with one input block `slack_link_code`, action id `value`, and the given callback id; `parse_link_submission` returns the trimmed code and returns an empty string when the block is absent. Verify: they fail.
- [x] 1.4 Add `build_link_modal(callback_id, code_lifetime)` and `parse_link_submission(payload)` to `backend/integrations/slack/modals.py`. Reuse `_input_value`. Update the module docstring. Verify: 1.3 passes and the existing capture modal tests pass unchanged.

## 2. Link flow (connections)

- [x] 2.1 In `backend/tests/test_slack_capture.py`, add a "Link shortcut" section with a `link_shortcut()` payload helper (type `shortcut`) and a `link_submission(code)` helper. Tests, each through the signed interactions endpoint:
  - unlinked actor: the opened view has `callback_id == "link_rescribo_account"` and a `slack_link_code` block, and no `SlackCaptureContext` row exists;
  - valid code: the response is an `update` titled "Account linked", `linked_membership` returns the member, and `GET identity/` reads linked;
  - empty code, unknown code, reused code, expired code, a code from another workspace, and a revoked member's code: each returns `errors` on `slack_link_code` and links nothing;
  - a code submitted from another team: refused, nothing linked;
  - a Slack user already linked to another member: refused with "This Slack account is already linked to another member.", both links unchanged;
  - already linked actor: the opened view is titled "Already linked" and has no input block;
  - team without an active connection: `open_view` is not called;
  - a bad signature on the shortcut and on the submission: 401, nothing stored.
  Verify: they fail on current code.
- [x] 2.2 In `backend/connections/slack_inbound.py`, add `LINK_CALLBACK_ID`, `start_link`, `submit_link`, and `submit_view` as `design.md` decisions 4 to 6 describe. `submit_link` calls `slack_identity.redeem_link_code` and adds no check of its own. Move the empty-code sentence to one constant used by both modals. Verify: no new query on `SlackLinkCode` or `ExternalIdentity` outside `slack_identity.py` (`grep -n "SlackLinkCode\|ExternalIdentity" backend/connections/slack_inbound.py` prints nothing).
- [x] 2.3 In `SlackInteractionsView.post` (`backend/connections/views.py`), inside the dispatch `try` block only: call `slack_inbound.submit_view` for `view_submission` and add a `shortcut` branch that calls `slack_inbound.start_link`. Verify: `git diff backend/connections/views.py` touches only that block, and 2.1 passes.
- [x] 2.4 Change `UNLINKED_TEXT` to name the "Link Rescribo account" shortcut. Update `test_member_revoked_after_the_modal_opened_cannot_submit` only if it asserts the sentence. Verify: `uv run pytest backend/tests/test_slack_capture.py backend/tests/test_slack_shortcut.py backend/tests/test_request_verification.py` passes, with every existing capture and linking test unchanged.

## 3. Settings text (frontend)

- [x] 3.1 In `frontend/src/features/settings/settings-page.test.tsx`, in "a member generates a Slack linking code and sees the link once made", assert the instructions name "Link Rescribo account" and do not name "Submit customer feedback". Verify: it fails.
- [x] 3.2 Change the sentence in `frontend/src/features/settings/slack-account.tsx` to the text in `design.md` decision 9. Verify: 3.1 passes.

## 4. Manifest and docs

- [x] 4.1 Add the `link_rescribo_account` global shortcut to `features.shortcuts` in `docs/slack-app-manifest.json`. Leave scopes and URLs alone. Verify: `python3 -m json.tool docs/slack-app-manifest.json` succeeds and the bot scopes are still the five in the spec.
- [x] 4.2 In `docs/PROVIDER_SETUP.md` section 8, add a short note: an existing app takes a changed manifest through **App Manifest** in the app settings or `apps.manifest.update`, and the manifest declares two shortcuts. Do not reword existing lines. Verify: the diff is additions only.

## 5. Screenshots

- [x] 5.1 Take the after screenshots as the brief describes and build the comparison page. The demo member is already linked, so the changed sentence does not appear in these screenshots. Say so in the PR.

## 6. Checks and archive

- [x] 6.1 Run `task check test build schema-check` with PostgreSQL and Redis running. Verify: all pass, and `task schema` produces no diff.
- [x] 6.2 Run `RESCRIBO_E2E_API_PORT=8149 RESCRIBO_E2E_FRONTEND_PORT=5149 task e2e`. Verify: it passes.
- [x] 6.3 Run `npx @fission-ai/openspec validate --all --strict`. Verify: it passes.
- [x] 6.4 Archive the change. Verify: `openspec/specs/slack-connection/spec.md` carries the modified requirement and the new one, and no other requirement's text changed.
- [x] 6.5 In the PR body, list the manifest steps and the six live checks from `design.md` under "Decisions to review", marked as not yet run. State that the tests are mocked and no live Slack call was made.
