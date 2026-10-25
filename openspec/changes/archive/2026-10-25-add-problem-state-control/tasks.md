# Tasks

## 1. API

- [x] 1.1 Add `ProblemStateChangeSerializer` (action choices from `PROBLEM_TRANSITIONS`, optional reason up to 2000 characters) and append `not_planned_reason` to `ProblemDetailSerializer`; verify with the tests in 1.3
- [x] 1.2 Add `ProblemStateChangeView(ProblemActionView)` calling `change_problem_state`, and the `problems/<uuid:problem_id>/state/` route named `problem-state`; verify with the tests in 1.3
- [x] 1.3 Add `backend/tests/test_problem_state_api.py` covering start, stop, decline with reason (shown in the detail response), reopen (reason cleared), blank decline reason (400 on `reason`), unknown action (400), `fix_available` decline (409 `invalid_transition` with `current`), stale version (409 `version_conflict`, state unchanged), another workspace's problem (404, unchanged), a demo workspace (200), CSRF required (403), and the activity entry; verify `uv run pytest backend/tests/test_problem_state_api.py` passes
- [x] 1.4 Add the new route to `ROUTES` in `backend/tests/test_workspace_isolation_api.py`; verify the isolation tests pass
- [x] 1.5 Run `task schema` on the current base, never hand-merging; verify `task schema-check` passes and `not_planned_reason` and the new request schema appear in `frontend/src/api/schema.d.ts`. After #183 merges, the coordinator rebases and regenerates the schema.

## 2. Status card

- [x] 2.1 Add `changeProblemState` to `frontend/src/api/problems.ts`; verify `npm run typecheck` passes from `frontend`
- [x] 2.2 Add `DeclineProblemForm` and `ProblemStatusCard` in `frontend/src/features/problems/problem-status.tsx` per design.md, and render the card first in the side column of `problem-detail-page.tsx`; verify with the tests in 2.3
- [x] 2.3 Add `problem-status.test.tsx` covering the actions per state, no card for `fix_available`, the reason shown for `not_planned`, confirm disabled on a blank reason, the typed reason kept after a 409, and focus on the card heading after success; verify `npm test` passes

## 3. No-reports offer

- [x] 3.1 Export one helper for "open or in progress with zero reports" from `problem-state.tsx`, use it in `NoReportsBadge`, and verify `problem-state.test.tsx` still passes
- [x] 3.2 In the linked reports empty text, show a "Mark not planned" button that opens `DeclineProblemForm` when the helper is true; add component tests for an empty open problem (offer shown), a problem with reports (no offer), and an empty `fix_available` problem (no offer); verify `npm test` passes
- [x] 3.3 Add a short "Problem status" section to `frontend/DESIGN.md` on the Status card and the shared decline form, without rewording existing text

## 4. Checks

- [x] 4.1 Run `task check test build schema-check` with PostgreSQL and Redis running; all pass
- [x] 4.2 Run `RESCRIBO_E2E_API_PORT=8181 RESCRIBO_E2E_FRONTEND_PORT=5181 task e2e`; all pass
- [x] 4.3 Take after screenshots per the brief, plus `SHOTS_BASE=http://127.0.0.1:5181 node .switchyard/shots/extra-shots.mjs .switchyard/shots/after` for the open, in-progress, and not-planned problems (the default shot is a `fix_available` problem, where the card is hidden), and build `.switchyard/shots/compare.html`
- [x] 4.4 Run `npx @fission-ai/openspec validate --all --strict`; passes

## Workflow follow-up

- Archive the change in the PR that completes it.
