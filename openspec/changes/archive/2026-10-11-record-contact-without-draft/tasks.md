# Tasks

Delivers #160. Write the tests first (groups 1 to 3), see the frontend ones fail, then make the change (group 4).

Do not edit `backend/feedback/follow_ups.py`, `backend/connections/slack_outcomes.py`, `RecipientForm`, `frontend/src/components/forms/`, or `frontend/src/components/states/action-error.tsx`. Append new tests; do not change existing ones except where a task says so. Rebase on main after #157 merges.

## 1. Server test in `backend/tests/test_follow_ups.py`

- [x] 1.1 Add `test_outcomes_without_a_notification_move_buckets` next to `test_then_confirmed_from_contacted`. With `fixed_report(owner, source=slack_source())` and no draft: assert the follow-up is in `needs_approval`; record `CONTACTED` then `CONFIRMED` with `_record`; assert it is in `completed`, absent from `needs_approval`, `awaiting_contact`, and `awaiting_confirmation`, and that no `ReportNotificationOperation` row exists for it.
- [x] 1.2 Add `test_recording_an_outcome_leaves_the_draft_alone`: call `draft_notification`, record `CONTACTED`, and assert the operation's `state`, `message`, `draft_version`, and `updated_at` are unchanged.
- [x] 1.3 Run `uv run pytest backend/tests/test_follow_ups.py -k "without_a_notification or leaves_the_draft"`. Both pass already; they pin behaviour the page now relies on.

## 2. Component tests in `frontend/src/features/follow-ups/follow-up-detail.test.tsx`

- [x] 2.1 Add `shows customer contact before a message is prepared`: `stubDetail()` (notification `null`), render the panel route, assert `region` "Customer contact" and `combobox` "Record outcome" are present. Repeat on the `/page` route.
- [x] 2.2 Add `records contact with no message prepared`: stub `POST ${base}/outcome/` to return `detail({ outcome: { state: 'contacted', note: '', at: '2026-09-20T10:00:01Z', by: ada }, version: 2 })`, submit the form untouched, assert the body is `{ state: 'contacted', note: '', expected_version: 1 }`, "Outcome: Contacted." shows, and Delivery still reads "Not prepared".
- [x] 2.3 Add `says contact is recorded when no message was prepared`: notification `null`, outcome `contacted`. Assert the Message region contains "Customer contact is already recorded" and the "Prepare message" button. With outcome `pending`, assert the sentence is absent.
- [x] 2.4 Run `cd frontend && npx vitest run src/features/follow-ups/follow-up-detail.test.tsx`. Verify the three new tests fail and the rest pass.

## 3. Browser test in `frontend/e2e/follow-ups.spec.ts`

- [x] 3.1 Add `records customer contact without preparing a message` at the end of the describe block: `ensureFollowUpOwner`, `confirmFix`, `openFollowUp`; do not click "Prepare message"; record "Customer contacted" in the Customer contact region; assert "Outcome: Contacted." and that the detail still contains "Not prepared"; open `/follow-ups`, select "Awaiting confirmation", assert the row is listed and contains "Not prepared"; select "Needs approval", assert it is not listed.
- [x] 3.2 In `records contact and then confirmation without touching the form again`, delete the comment "The contact section appears once the message is prepared. Nothing is sent." It is no longer true. Leave the code.

## 4. Change in `frontend/src/features/follow-ups/follow-up-detail.tsx`

- [x] 4.1 In `FollowUpBody`, build `contact` unconditionally as `<ContactSection ... />`. In the panel layout, render `<Separator />` and `{contact}` without the `contact ? ... : null` wrapper.
- [x] 4.2 In `DraftSection`, when `followUp.outcome.state !== 'pending'`, add one muted paragraph above the button: `Customer contact is already recorded. Prepare a message only if {memberName(followUp.recipient.member)} still needs it.` Depends on open question 2.
- [x] 4.3 Rerun 2.4: all pass. Run 3.1 with `RESCRIBO_E2E_API_PORT=8160 RESCRIBO_E2E_FRONTEND_PORT=5160 npx playwright test e2e/follow-ups.spec.ts -g "without preparing a message"`: passes.

## 5. Repository checks

- [x] 5.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 5.2 `task check test build schema-check` passes with PostgreSQL and Redis running (ports in `.claude/brief.md`; do not start or stop services). `schema-check` must report no API change. Record the counts.
- [x] 5.3 `RESCRIBO_E2E_API_PORT=8160 RESCRIBO_E2E_FRONTEND_PORT=5160 task e2e` passes. Record the counts.
- [x] 5.4 Take after screenshots into `.claude/shots/after` as the brief describes. No dev server is left on 8160 or 5160.

## Workflow follow-up

- Archive this change in the PR that completes #160 (`/opsx:archive`). The archive adds one requirement to `openspec/specs/follow-ups/spec.md` and rewords nothing.
- PR milestone: G. Manual check findings.
- PR "Decisions to review": the draft is left alone on an outcome; the Message section wording; members who may not record now see the form on every follow-up (existing 409).
