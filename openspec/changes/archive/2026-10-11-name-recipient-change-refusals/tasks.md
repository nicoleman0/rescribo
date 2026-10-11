# Tasks

Delivers #157. Read `design.md` first. Do not touch the customer contact or notification sections (#160), `frontend/src/components/forms/`, `frontend/src/api/request.ts` (#146), or `frontend/src/components/states/action-error.tsx`.

In each group, write the tests first and see them fail.

## 1. Refusal reasons (backend)

- [x] 1.1 In `backend/tests/test_follow_ups.py`, change `test_recipient_change_requires_slack_link_for_new_recipient` to expect `RecipientNotLinked`, and `test_recipient_change_requires_active_member` to expect `InvalidReference` with `field == "new_recipient"`. Add a test that naming the current recipient raises `NoChanges`. Each of the three asserts the recipient, the draft notification state, and the count of `recipient_changed` activities are unchanged. Verify: the three tests fail on current code.
- [x] 1.2 Add endpoint tests next to `test_recipient_change_endpoint_round_trip`: unlinked member answers 400 with `reason == "recipient_not_linked"`, `field_errors == {}`, the `detail` sentence from `design.md`, and no `current` key; current recipient answers 409 `no_changes` with `current`; a revoked member and a member of another workspace both answer 400 `invalid_reference` with `field_errors == {"new_recipient_id": ["invalid_reference"]}` and identical bodies; a follow-up with a recorded `confirmed` outcome accepts a linked member with 200. Verify: they fail on current code, except the last, which passes.
- [x] 1.3 Add `RecipientNotLinked` to `backend/feedback/errors.py` (reason `recipient_not_linked`) and its 400 branch to `feedback_error_response` in `backend/feedback/http.py`.
- [x] 1.4 In `backend/feedback/follow_ups.py`, add the private Slack identity queryset helper and use it in `has_slack_identity` and `change_recipient`. In `change_recipient` raise `InvalidReference(field="new_recipient")`, `RecipientNotLinked`, and `NoChanges` for the three causes. Keep the non-owner guard and the row locks. Check "already the recipient" before "no Slack link", so an unlinked current recipient reads `no_changes`. Verify: groups 1.1 and 1.2 pass and `uv run pytest backend/tests/test_follow_ups.py backend/tests/test_slack_outcomes.py` passes.
- [x] 1.5 Document 409 on the recipient endpoint's `extend_schema`, as the other follow-up endpoints do. Verify: `task schema` adds 409 to `follow-ups/{id}/recipient/` in `frontend/openapi.yaml`.

## 2. Member directory flag (backend)

- [x] 2.1 In `backend/tests/test_feedback_api.py`, extend the directory test: rows have exactly `id`, `display_name`, `has_slack_link`; a member with a Slack identity reads `true`, others `false`. Add a query-count assertion that the directory uses the same number of queries for two members and for five. Verify: fails on current code.
- [x] 2.2 Add `with_slack_link(members)` beside `has_slack_identity` in `follow_ups.py`: it annotates `has_slack_link` with `Exists` over the helper from 1.4. Add `MemberDirectoryEntrySerializer(MemberSummarySerializer)` with a `has_slack_link` boolean in `serializers.py`. `MemberDirectoryView` serializes `with_slack_link(workspace_directory(actor=...))` with it. Do not change `MemberSummarySerializer` or `workspace_directory`. Verify: 2.1 passes and `backend/tests/test_workspace_isolation_api.py` still passes.
- [x] 2.3 Run `task schema`. Verify: `frontend/openapi.yaml` gains `MemberDirectoryEntry`, `MemberSummary` is unchanged, and `task schema-check` passes.

## 3. Recipient picker and refusal text (frontend)

- [x] 3.1 In `frontend/src/api/reports.ts`, export `MemberDirectoryEntry = Schemas['MemberDirectoryEntry']` and type `listMembers` with it. Change nothing else in the file. Verify: `npm run typecheck` passes with no edits to other pickers.
- [x] 3.2 In `frontend/src/features/follow-ups/follow-up-detail.test.tsx`, stub the directory with entries that carry `has_slack_link` in the recipient tests, and add tests: an unlinked member's option is disabled and reads "<name> (no Slack link)"; the current recipient's option is enabled even when unlinked, and carries the label; a 400 `recipient_not_linked` shows the title "The recipient was not changed" with the server's `detail`, keeps the owner's selection, and refetches `members/`; a 400 `invalid_reference` shows "Choose an active record in this workspace." under the select. Leave the stubs of other tests alone. Verify: the new tests fail on current code and the existing "lets an owner change the recipient" test still passes.
- [x] 3.3 In `RecipientForm`, render each option as disabled when `!member.has_slack_link && member.id !== saved`, append " (no Slack link)" to the text of any unlinked member, and refetch members in the `onError` of `mutation.mutate`. Keep the fallback option for a saved recipient who is not in the directory. Verify: 3.2 passes and `npm run test -- follow-up-detail` passes.
- [x] 3.4 Add one line to "Follow-up page" in `frontend/DESIGN.md`: the Recipient picker lists every active member, and a member with no Slack link is a disabled option that ends "(no Slack link)". Do not reword existing lines. Verify: the diff of `DESIGN.md` is additions only.
- [x] 3.5 Add one browser test to `frontend/e2e/follow-ups.spec.ts`: as an owner, open a follow-up and assert the Recipient picker has a disabled option ending "(no Slack link)" (in the e2e seed the six owners have a Slack link and the two members, "Member", do not) and an enabled option for a linked member. Reuse `confirmFix`, `openFollowUp`, and the saved owner session. Verify: `RESCRIBO_E2E_API_PORT=8157 RESCRIBO_E2E_FRONTEND_PORT=5157 task e2e` passes.

## 4. Screenshots

- [x] 4.1 With the dev servers from `.claude/brief.md` running, run `uv run python backend/manage.py shell < .claude/shots/recipient-seed.py`, then `SHOTS_BASE=http://127.0.0.1:5157 node .claude/skills/work-issues/scripts/shots.mjs .claude/shots/after` and `SHOTS_BASE=http://127.0.0.1:5157 node .claude/shots/recipient-shots.mjs .claude/shots/after`. The planner's before shots are in `.claude/shots/before`. Verify: `recipient-form-*` in `after` shows "Una Unlinked (no Slack link)" greyed out, and the script logs that option as disabled. `recipient-refused-*` has no after shot, because the picker no longer lets the owner reach the refusal. Build `.claude/shots/compare.html` with `compare.py`. Stop the servers.

## 5. Checks

- [x] 5.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 5.2 `task check test build schema-check` passes with PostgreSQL and Redis running. Record the test counts for the PR.
- [x] 5.3 `RESCRIBO_E2E_API_PORT=8157 RESCRIBO_E2E_FRONTEND_PORT=5157 task e2e` passes. Record the counts.
- [x] 5.4 Write the PR body with the sections from `.claude/brief.md`. Under "Decisions to review", list: 400 and 409 `no_changes` replace 409 `invalid_transition`; 400 `invalid_reference` replaces 404; the Slack link flag is visible to every member; a member linked to a different Slack team still counts as linked; the non-owner guard in the use case is unchanged.

## Workflow follow-up

- Archive the change in the PR that completes it (`/opsx:archive`).
