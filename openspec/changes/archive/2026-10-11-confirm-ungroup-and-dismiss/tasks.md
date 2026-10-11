# Tasks

Delivers #161. Paths are from the repository root. Decisions D1 to D9 are in `design.md`. Frontend only: do not touch the backend, `frontend/openapi.yaml`, or `frontend/src/api/schema.d.ts`.

Do not touch `frontend/src/features/problems/` (#162), `frontend/src/components/forms/` (#146), or `frontend/src/dev/ui-gallery.tsx`.

Group 1 is a refactor with no behaviour change. Finish it and see the settings tests pass before starting group 2. Keep the two in separate commits.

## 1. Shared `ConfirmPanel` (refactor)

- [x] 1.1 Add `frontend/src/components/confirm/confirm-panel.tsx` with the props in D2. Move the `<form>` box, title, description, and Confirm and Cancel row from `ConfirmAction` with their classes unchanged. `children` render between the description and the button row. The form's accessible name is `title`. Verify with 1.2.
- [x] 1.2 Add `frontend/src/components/confirm/confirm-panel.test.tsx`: the title renders at `headingLevel` (3 by default, 4 when asked); the confirm button is disabled when `confirmDisabled` or `isPending`, and reads `pendingLabel` while pending; Cancel is disabled while pending; submit calls `onConfirm` and Cancel calls `onCancel`; with `focusOnOpen` the title has focus after mount, and without it the title has no `tabindex`. Verify with `npm test -- confirm-panel` from `frontend`.
- [x] 1.3 Change `frontend/src/features/settings/confirm-action.tsx` to render `ConfirmPanel` per D2. Keep its trigger, open state, phrase, mutation, and cancel logic. Do not pass `focusOnOpen`. Verify that `npm test -- settings` passes with no edit to any settings test, and that `git diff --stat` shows no settings test file.

## 2. Confirm step in `frontend/src/features/inbox/report-actions.tsx`

Write the tests first (2.1 to 2.3), see them fail, then build 2.4 to 2.8. Tests go in `frontend/src/features/inbox/report-actions.test.tsx` and reuse `stubReport`, `accept`, `triage`, and `routes`. A linked report is `{ ...report, triage_state: 'linked', problem: { id: 'prob-1', title: 'Exports fail', state: 'open' } }`.

- [x] 2.1 Change the existing test "locks actions while a dismissal is pending": click "Dismiss", then "Dismiss report". Assert the confirm button reads "Saving…" and is disabled and Cancel is disabled. Drop the "Link to problem" assertion, because the row is hidden while the step is open. Keep the second click on "Saving…" and `sent` of length 1.
- [x] 2.2 Add tests for the open and confirm paths:
  - Dismiss asks first: after clicking "Dismiss", the form named "Dismiss this report?" shows "You can restore it later", its level 4 heading has focus, and `sent` is empty. Clicking "Dismiss report" sends `{ path: 'dismiss', body: { expected_version: 3 } }`, shows "Restore report", and focuses the Triage heading.
  - Ungroup names the side effect: on a linked report, the form named "Ungroup this report?" contains "unsent employee notification" and "Sent history is kept". Confirming sends `unlink` and shows "Link to problem".
  - Cancel: no request is sent, the action row shows again, and the "Ungroup" button has focus (use `waitFor`, as the existing cancel test does).
  - Repeated Enter: with `userEvent`, focus "Dismiss" and type `{Enter}{Enter}`. The form is open and `sent` is empty.
- [x] 2.3 Add tests for failures:
  - Network failure: the first `unlink` throws `TypeError('Failed to fetch')`. The form stays open and shows "The report was not updated" and "Could not reach Rescribo" inside it. Confirming again succeeds.
  - Edited meanwhile: the first `dismiss` answers 409 with `current` set to the report with `assignee: grace, version: 5`, still `new`. The form stays open with "changed while you were working". Confirming again sends `expected_version: 5`.
  - Action no longer applies: on a linked report, `unlink` answers 409 with `current` set to the report as `new`, `problem: null`, `version: 5`. Also stub `dismiss`. Assert the form is gone, "Dismiss" and "The report was not updated" show, and `sent` holds only the `unlink` call.
  - Lost dismiss: on a new report, `dismiss` answers 409 with `current` set to the report as `dismissed`. Assert "Restore report" and "The report was not updated" show, and "The report was not restored" does not.
- [x] 2.4 Extend `Panel` with `'unlink'` and `'dismiss'`. Add a ref on the third button. Its click resets the mutation and opens the step for `linked ? 'unlink' : 'dismiss'`. The button always reads "Ungroup" or "Dismiss".
- [x] 2.5 Render `ConfirmPanel` for the open step with the wording in D8, `headingLevel={4}`, `focusOnOpen`, `pendingLabel="Saving…"`, and `isPending={transition.isPending}`. `onConfirm` calls `transition.mutate(panel)` (D5). `onCancel` resets the mutation and calls `close` with the third button's ref.
- [x] 2.6 Pass `finish` as the mutation's success callback so the step closes and the Triage heading takes focus.
- [x] 2.7 Close an open confirm step when `report.triage_state` changes, per D6. Leave link and create panels open.
- [x] 2.8 Errors per D7: `ActionError` inside the step while it is open, the block under the row otherwise, and the dismissed branch's title from `transition.variables`. Show the linked hint whenever the action row shows. Verify with `npm test -- report-actions` from `frontend`: all of 2.1 to 2.3 pass and no other test in the file changed.

## 3. E2E and design notes

All in `frontend/e2e/report-triage.spec.ts`. No other e2e spec clicks Ungroup or Dismiss. The existing waits on `{ name: 'Ungroup' }` (lines 73, 132, 163, 345) and the touch target loop (line 396) stay as they are.

- [x] 3.1 In "groups two reports into one problem, then moves, reassigns, ungroups, dismisses, and restores": click "Ungroup" with `exact: true`, then "Ungroup report". For Dismiss, first `dblclick` "Dismiss" (`exact: true`) and assert the form "Dismiss this report?" is visible and the detail still shows "New", then click "Dismiss report". Restore stays one click.
- [x] 3.2 In "is keyboard operable, accessible, and fits a phone", once the report is linked at 1280px: focus "Ungroup" and press Enter; assert the heading "Ungroup this report?" is focused and `axeViolations(page)` is empty. Press Enter again and assert the form is still visible. Press Tab and assert "Ungroup report" is focused. Press Tab, assert Cancel is focused, press Enter, and assert "Ungroup" is focused. Then `dblclick` "Ungroup", assert the form is visible, and cancel. The report must stay linked for the rest of the test.
- [x] 3.3 In the same test at 375px, after the existing touch target loop: open the Ungroup step, run `expectTouchTarget` on "Ungroup report" and Cancel, assert no horizontal overflow, cancel, then `dblclick` "Ungroup", assert the form is visible, and cancel. If a `dblclick` check fails because a step button sits under the trigger, stop and ask (see Risks in `design.md`).
- [x] 3.4 Add two bullets to `frontend/DESIGN.md` and reword nothing. Under "Components": "ConfirmPanel: the inline confirm step for an action with a side effect; settings adds a typed phrase for permanent deletion". Under "Inbox": "Ungroup and Dismiss open a confirm step in place of the triage actions. Focus goes to its title, and Cancel returns it to the button." Verify with `git diff frontend/DESIGN.md`: two added lines, none removed.
- [x] 3.5 After screenshots. Reseed with `RESCRIBO_DEMO_PASSWORD='Rescribo-demo-e2e-2026!' uv run python backend/manage.py seed_demo`, start the dev servers on 8161 and 5161, then run `SHOTS_BASE=http://127.0.0.1:5161 node .claude/skills/work-issues/scripts/shots.mjs .claude/shots/after` and `SHOTS_CONFIRM=1 SHOTS_BASE=http://127.0.0.1:5161 node .claude/shots/triage-shots.mjs .claude/shots/after`. Build `.claude/shots/compare.html` with `.claude/skills/work-issues/scripts/compare.py` from the `triage-linked-confirm-*`, `triage-new-confirm-*`, and `settings-*` shots. The before folder already holds `triage-*-confirm-*` files: they are copies of the screen before the click, because before this change the click applied at once. Say so in the page intro. Stop the dev servers.

## 4. Repository checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 4.2 `task check test build schema-check` passes with PostgreSQL and Redis running, and `schema-check` reports no contract change.
- [x] 4.3 `RESCRIBO_E2E_API_PORT=8161 RESCRIBO_E2E_FRONTEND_PORT=5161 task e2e` passes.

## Workflow follow-up

- Archive the change in the PR that completes it.
