# Tasks

Delivers #209. Refactor; `skip_specs: true`. Touch only `frontend/src/features/follow-ups/`.

Rules for every task:

- Move code as it is. Do not rename, reorder inside a function, reword, or reformat.
- The only new text is `export` in front of a moved declaration and import lines. Exception, decided during implementation: Prettier reflowed two declarations in `follow-up-detail.fixtures.tsx`, `ada` and `detail`, because `export ` pushed them past 80 columns.
- Do not change a test title, body, or assertion.
- Keep the order the declarations and tests have in the old file.
- All paths below are under `frontend/src/features/follow-ups/`.

## 1. Split `follow-up-detail.tsx`

- [x] 1.1 Create `follow-up-layout.ts`. Move `wrapLongText`, `FollowUpLayout`, `FollowUpLayoutContext`, and `useSectionClass` into it and export all four.
- [x] 1.2 Create `follow-up-section-heading.tsx`. Move `SectionHeading` into it and export it.
- [x] 1.3 Create `follow-up-message-editor.tsx`. Move `MessageEditor`, `ApproveButton`, and `MessagePreview` into it. Export `MessageEditor` and `MessagePreview`.
- [x] 1.4 Create `follow-up-message.tsx`. Move `MessageSection`, `DraftSection`, `QueuedSection`, `SentSection`, `FailedSection`, and `UncertainSection` into it. Export `MessageSection`.
- [x] 1.5 Create `follow-up-outcome.tsx`. Move `choicesFor`, `ContactSection`, `RecordOutcomeForm`, and `CorrectionForm` into it. Export `ContactSection`.
- [x] 1.6 Create `follow-up-recipient-form.tsx`. Move `RecipientForm` into it and export it.
- [x] 1.7 Create `follow-up-history.tsx`. Move `FollowUpHistory` and `describeHistory` into it. Export `FollowUpHistory`.
- [x] 1.8 `follow-up-detail.tsx` keeps `QUEUED_POLL_MS`, `FollowUpDetailPanel`, `FollowUpDetailContent`, `FollowUpBody`, and `FollowUpSummary`. Import `MessageSection`, `ContactSection`, `RecipientForm`, `FollowUpHistory`, and the layout helpers it uses. Remove imports it no longer uses.
- [x] 1.9 Verify: no new file imports `./follow-up-detail` (`grep -l "from './follow-up-detail'" *.tsx *.ts` lists only `follow-up-detail-page.tsx`, `follow-ups-page.tsx`, and test files). `follow-ups-page.tsx` and `follow-up-detail-page.tsx` are unchanged.
- [x] 1.10 Run from `frontend`: `npm run typecheck` and `npx vitest run src/features/follow-ups`. Verify: typecheck passes and the unsplit test file reports 32 passed. This shows the source split alone changes nothing.

## 2. Split `follow-up-detail.test.tsx`

Every test file imports what it uses from `./follow-up-detail.fixtures` and from the libraries. No test file imports `./follow-up-detail` except through the fixtures' `routes`.

- [x] 2.1 Create `follow-up-detail.fixtures.tsx`. Move `base`, `csrfPath`, `ada`, `grace`, `routes`, `notification`, `detail`, `stubDetail`, and `definitionOf` into it and export all nine.
- [x] 2.2 `follow-up-detail.test.tsx` keeps these 4 tests:
  - labels delivery and outcome and lists the follow-up details
  - shows delivery as not prepared before a message exists
  - uses page heading levels and page section layout
  - links from the panel to the full page with the current query
- [x] 2.3 Create `follow-up-message.test.tsx` with `messageRegion` and these 6 tests:
  - says contact is recorded when no message was prepared
  - shows the queued status and stops polling once sent
  - shows a delivered message with a confirmation when the recipient confirmed by hand
  - shows Retry when the send failed
  - offers mark delivered, send again with confirmation, and cancel for uncertain
  - labels a delivered message in the demo as simulated
- [x] 2.4 Create `follow-up-message-editor.test.tsx` with these 5 tests:
  - drafts the default message then edits it before approving
  - keeps an edited draft on the page when the edit fails
  - keeps approval disabled while the edit is saving
  - queues the send when a member clicks Send to Slack
  - offers copy-to-clipboard when the recipient has no Slack link
- [x] 2.5 Create `follow-up-outcome.test.tsx` with `OutcomeState`, `outcomeDetail`, `stubOutcomes`, `outcomeSelect`, `noteBox`, `reasonBox`, and these 10 `test` calls (11 tests, one runs for two paths):
  - shows customer contact before a message is prepared at %s
  - records contact with no message prepared
  - records an outcome and requires a note for no response
  - disables the submit button until a note is provided for no response
  - offers correction to an owner for a terminal outcome
  - blocks an owner correction that omits a reason
  - records contact and then confirmation without a reload
  - records an outcome after a correction back to pending
  - corrects an outcome twice without a reload
  - keeps the note when another member changed the outcome first
- [x] 2.6 Create `follow-up-recipient-form.test.tsx` with these 4 tests:
  - lets an owner change the recipient
  - shows unlinked recipients disabled and keeps an unlinked current recipient enabled
  - shows the server reason and refetches members after a recipient refusal
  - shows an invalid recipient under the select
- [x] 2.7 Create `follow-up-history.test.tsx` with these 2 tests:
  - renders the history feed
  - uses section-level headings for panel history
- [x] 2.8 Run from `frontend`: `npx vitest run src/features/follow-ups/follow-up-`. Verify: 7 test files (the six above and `follow-up-detail-page.test.tsx`), and the six report 4, 6, 5, 11, 4, and 2 passed, 32 in total.

## 3. Prove the code only moved

Run from the repository root with `bash`. `$F` is `frontend/src/features/follow-ups`.

- [x] 3.1 Source. Both commands print nothing but import lines. The first lists old lines missing from the new files. The second lists lines the new files add.

  ```bash
  F=frontend/src/features/follow-ups
  old() { git show HEAD:$F/follow-up-detail.tsx | sed 's/^export //' | sort; }
  new() { cat $F/follow-up-detail.tsx $F/follow-up-layout.ts $F/follow-up-section-heading.tsx \
    $F/follow-up-message.tsx $F/follow-up-message-editor.tsx $F/follow-up-outcome.tsx \
    $F/follow-up-recipient-form.tsx $F/follow-up-history.tsx | sed 's/^export //' | sort; }
  comm -23 <(old) <(new)
  comm -13 <(old) <(new)
  ```

  Verify: every line printed is part of an import statement or a blank line. If a line of component code appears, the move changed it. Fix the move, not the check.

- [x] 3.2 Tests. Same check for the test files.

  ```bash
  old() { git show HEAD:$F/follow-up-detail.test.tsx | sed 's/^export //' | sort; }
  new() { cat $F/follow-up-detail.fixtures.tsx $F/follow-up-detail.test.tsx \
    $F/follow-up-message.test.tsx $F/follow-up-message-editor.test.tsx \
    $F/follow-up-outcome.test.tsx $F/follow-up-recipient-form.test.tsx \
    $F/follow-up-history.test.tsx | sed 's/^export //' | sort; }
  comm -23 <(old) <(new)
  comm -13 <(old) <(new)
  ```

  Verify: every line printed is part of an import statement or a blank line, apart from the reflowed `ada` and `detail` declarations in the fixtures file. If any other line of test code appears, the move changed it. Fix the move, not the check.

- [x] 3.3 `git status --short` lists only files under `frontend/src/features/follow-ups/` and `openspec/changes/`. `frontend/package.json` and `frontend/package-lock.json` are unchanged.
- [x] 3.4 From `frontend`: `npx oxlint src/features/follow-ups` reports no warning and no error, as it does before the change. `npx prettier --check src/features/follow-ups` passes.

## 4. Repository checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 4.2 `task check test build schema-check` passes with PostgreSQL and Redis running (see `.claude/brief.md` for the ports; do not start or stop services). Record the test counts for the PR. The frontend test count equals the count on `main`. `schema-check` reports no API change.
- [x] 4.3 `RESCRIBO_E2E_API_PORT=8209 RESCRIBO_E2E_FRONTEND_PORT=5209 task e2e` passes with no edit to any file under `frontend/e2e/`. Record the counts for the PR.
- [x] 4.4 No dev server is left on 8209 or 5209.

## Workflow follow-up

- Archive this change in the PR that completes #209 (`/opsx:archive`).
- PR milestone: H. Product-grade UI.
- PR "Decisions to review": the eight source files and what each holds; `MessagePreview` lives with the editor; the layout helpers are in a `.ts` file to keep lint clean; tests still render the whole detail and share a fixtures file.
- PR body lists the items under "Out of scope" in `design.md` as noticed, not changed.
- PR Screenshots: "Not applicable: no visible change". Take screenshots only if a check shows a visual difference.
