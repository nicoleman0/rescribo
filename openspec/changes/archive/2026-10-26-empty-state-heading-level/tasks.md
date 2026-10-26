# Tasks

Write each test first and see it fail against the current `h1` before changing the code it covers.

## 1. Level 2 by default, for list pages and panels

- [x] 1.1 In `async-states.test.tsx`, assert `EmptyState` renders its title as a level-2 heading by default and as level 1 with `level={1}`, and that `QueryState status="empty"` renders a level-2 title; verify the tests fail
- [x] 1.2 In `inbox-page.test.tsx`, extend the "No reports yet" and "Report not found" tests to assert exactly one level-1 heading ("Inbox") and a level-2 state title; verify they fail (two `h1` today)
- [x] 1.3 Do the same in `problems-page.test.tsx` for "No problems yet" (one `h1`, "Problems") and in `follow-ups-page.test.tsx` for "No follow-ups yet" (one `h1`, "Follow-ups"); verify they fail
- [x] 1.4 In `follow-ups-page.test.tsx`, add a case for a follow-up panel whose detail returns 404, and assert one `h1` ("Follow-ups") and a level-2 "Follow-up not found"; verify it fails
- [x] 1.5 Add `level?: 1 | 2` (default 2) to `EmptyState` in `async-states.tsx`, keeping the title's classes; verify every test from 1.1 to 1.4 passes

## 2. Whole-page states (level 1)

- [x] 2.1 In `App.test.tsx`, assert an unknown path shows "Page not found" as the only level-1 heading; verify it fails after 1.5, then pass `level={1}` in `App.tsx` and verify it passes
- [x] 2.2 In `require-auth.test.tsx`, assert a session with no memberships shows "Workspace access removed" as the only level-1 heading, inside a `main` landmark; verify it fails, then pass `level={1}` in `require-auth.tsx`, wrap the state in `<main>` like the error branch beside it, and verify it passes
- [x] 2.3 In `problems-page.test.tsx`, extend the "Problem not found" test to assert it is the only level-1 heading; verify it fails, then pass `level={1}` to both states in `problem-detail-page.tsx` and verify it passes
- [x] 2.4 In `follow-up-detail-page.test.tsx`, extend the "Follow-up not found" test to assert it is the only level-1 heading; verify it fails, then set the level from `layout` in `FollowUpDetailContent` (page → 1, panel → 2) and verify both this test and 1.4 pass
- [x] 2.5 Add a short "Empty state headings" section to `frontend/DESIGN.md`: the title is `h2` under a page heading; pass `level={1}` only when the state is the whole page. Do not reword existing text

## 3. Repository checks

- [x] 3.1 Run `npx @fission-ai/openspec validate --all --strict` and verify it passes
- [x] 3.2 With PostgreSQL and Redis running, run `task check test build schema-check` and verify all pass
- [x] 3.3 Run `RESCRIBO_E2E_API_PORT=8236 RESCRIBO_E2E_FRONTEND_PORT=5236 task e2e` and verify it passes, including the axe checks in `z-product-states.spec.ts`

## Workflow follow-up

- In the PR, list every `EmptyState` call site and its level, as in the design's table.
- Archive the change in the PR that completes it.
