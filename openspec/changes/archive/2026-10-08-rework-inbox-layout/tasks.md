# Tasks

## 1. List rows

- [x] 1.1 Rework `report-list.tsx` rows into a single-line grid with the status badge first, the assignee avatar, and a short date, collapsing to two lines under a container query; verify `inbox-page.test.tsx` asserts the badge precedes the title and the assignee name is in the row's accessible text.

## 2. Filters

- [x] 2.1 Add status chips with counts from one list query per state, with loading, unavailable, and retry states, and remove the Status select; verify unit tests cover a chip setting `triage_state`, counts that follow the customer filter, and a failed count.
- [x] 2.2 Put the customer field, chips, assignee, and source behind a Filters button below `md`, showing the number of active filters; verify a unit test for `aria-expanded` and the active count.

## 3. Report panel

- [x] 3.1 Widen the panel, make it sticky on `lg`, render "Back to reports" as a corner close icon on `lg`, and move triage above the details with grouping before assignee; verify `report-actions.test.tsx` and the existing panel tests pass.

## 4. Documentation and e2e

- [x] 4.1 Append the inbox layout rules to `frontend/DESIGN.md`; verify they name only existing tokens and components.
- [x] 4.2 Update `e2e/inbox.spec.ts` and `e2e/report-triage.spec.ts` selectors only where markup changed, and add a phone-width check that the first report is visible without scrolling; verify with `task e2e` on ports 8107 and 5107.

## 5. Repository checks

- [x] 5.1 Run `npx @fission-ai/openspec validate --all --strict`, `task check test build schema-check` with PostgreSQL and Redis running, and `task e2e`; verify all pass.
- [x] 5.2 Take after screenshots of every screen in light and dark at 1280px and 390px and build the before/after comparison page.

## Workflow follow-up

- Suggested problem in the report panel is left to #21.
- Archive this change in the PR that completes issue #107.
