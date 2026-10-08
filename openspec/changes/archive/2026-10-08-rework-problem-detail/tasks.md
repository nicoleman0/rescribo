# Tasks

## 1. Activity

- [x] 1.1 Add `groupActivity` and the field and GitHub event labels in `src/features/problems/`; verify unit tests cover a batch of links, a move breaking a batch, another actor breaking a batch, the 10-minute gap, and the `needs_review` label.
- [x] 1.2 Render grouped entries as "linked N reports" with a disclosure listing the report links; verify a component test expands the group and finds each title.

## 2. Next step and side column

- [x] 2.1 Add `ProblemNextStep` with the state and needs-review table from design.md; verify unit tests render each row's tone, heading, and links.
- [x] 2.2 Move the fix (confirm form or confirmed fix), GitHub issue, and owner into side-column cards, with the owner shown as text and Change opening the form; verify a component test saves an owner, closes the form, and keeps it open on a failed save.

## 3. Linked reports

- [x] 3.1 Add `ReportAssigneeEditor` in `features/problems/`: assignee as text, Change opens the unchanged `AssignReportForm`, and a Done button outside the form closes it; verify a component test reassigns a report, and that a failed save keeps the form and error open until Done.
- [x] 3.2 Replace the per-report card with compact rows (title, badge, customer, source line, `ReportAssigneeEditor`, Confirm fix applies) and drop `Provenance` from this page, without editing any file in `features/inbox/`; verify `git diff --stat` shows no inbox changes and the component test for rows passes.
- [x] 3.3 Update `e2e/report-triage.spec.ts` and `e2e/follow-ups.spec.ts` for the new layout, and in `e2e/themes.spec.ts` replace `axeViolations(page, ['color-contrast'])` with `axeViolations(page)` and delete the comment above it; verify `task e2e` passes on ports 8108 and 5108.
- [x] 3.4 Append a "Problem detail" section to `frontend/DESIGN.md` covering the next-step banner and edit on demand; verify every name it mentions exists in code.

## 4. Repository checks

- [x] 4.1 Run `npx @fission-ai/openspec validate --all --strict`, `task check test build schema-check` with PostgreSQL and Redis running, and `RESCRIBO_E2E_API_PORT=8108 RESCRIBO_E2E_FRONTEND_PORT=5108 task e2e`; verify all pass.
- [x] 4.2 Take after screenshots in light and dark at desktop and phone width, check them, and build the before/after comparison page.

## Workflow follow-up

- Sync the delta into `openspec/specs/web-interface/spec.md` and archive this change in the PR that completes issue #108.
