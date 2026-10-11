# Tasks

Paths are from the repository root. Decisions D1 to D6 are in `design.md`. Do not start until the coordinator has answered the Open Questions there.

## 1. Badge

- [x] 1.1 In `frontend/src/features/problems/problem-state.tsx`, add `NoReportsBadge({ problem })` per D1 and D2. `problem` is `Pick<ProblemListItem, 'state' | 'report_count'>` from `@/api/problems`. It returns `null` unless `state` is `open` or `in_progress` and `report_count` is `0`; otherwise `<StatusBadge tone="warning">No reports</StatusBadge>`. One comment line saying why settled problems are skipped. Verify in `problem-state.test.tsx` with one `test.each`: `open` and `in_progress` at count 0 render "No reports" with `data-tone="warning"`; `fix_available` and `not_planned` at count 0, and `open` at count 1, render nothing.

## 2. Problems list

- [x] 2.1 In `ProblemList` in `frontend/src/features/problems/problems-page.tsx`, render `<NoReportsBadge problem={problem} />` directly after `<ProblemStateBadge state={problem.state} />`. Change nothing else in the row; the "0 reports" text stays (D3). Verify with a new test in `problems-page.test.tsx`: the list returns `{ ...listItem, id: 'prob-2', title: 'Empty', report_count: 0, needs_review: false }` and `{ ...listItem, id: 'prob-3', title: 'Declined', state: 'not_planned', report_count: 0 }`. The "Empty" link holds "No reports" and "0 reports". The "Declined" link holds "0 reports" and no "No reports". The existing list test still passes, with no "No reports" on its row.
- [x] 2.2 Append one bullet to the "Problems list" section of `frontend/DESIGN.md`: an open or in-progress problem with no linked reports shows `NoReportsBadge` after its state, in the warning tone; settled problems do not; the count text stays. This file is shared: add the bullet, do not reword existing text. Verify: `git diff frontend/DESIGN.md` shows only added lines.

## 3. Problem detail

- [x] 3.1 In `ProblemHeader` in `frontend/src/features/problems/problem-detail-page.tsx`, render `<NoReportsBadge problem={problem} />` directly after `<ProblemStateBadge state={problem.state} />`. Leave `LinkedReports` and `ProblemNextStep` unchanged. Verify in `problems-page.test.tsx`: give `stubDetail` a second parameter `reports: ReportDetail[] = [linkedReport]` for the reports route. With `stubDetail({ ...detail, state: 'in_progress', report_count: 0 }, [])` the page shows "No reports" (exact match, warning tone) and "No reports are linked. The problem and its history are kept. Link a report from the Inbox." With the default `detail` (count 1) the page shows no exact "No reports".

## 4. Picker

- [x] 4.1 Add `frontend/src/features/problems/problem-picker.test.tsx`. Do not change `problem-picker.tsx` (D5). Render `<ProblemPicker workspaceId="ws-1" onSelect={onSelect} />` through `renderWorkspaceRoutes` with the list route stubbed to return one open problem with `report_count: 0`. Verify: its radio is enabled, the row reads "0 reports", choosing it calls `onSelect` with that problem, and the row holds no "No reports" badge.

## 5. Backend test

- [x] 5.1 Add one test to `backend/tests/test_feedback_triage_api.py` for the `problems` requirement. No production code changes. Make two problems. Move the first to `in_progress` with `change_problem_state(action="start")`. Link one report to the first, then link the same report to the second (a move), then ungroup it. Verify through `GET problems/<id>/` and `GET problems/`: the first is `in_progress` with `report_count == 0`, the second is `open` with `report_count == 0`, both are still in the list, and `GET problems/<id>/activity/` for the second still returns its `report.linked` and `report.unlinked` entries. Verify `uv run python backend/manage.py makemigrations --check` reports no changes.

## 6. Screenshots

- [x] 6.1 The seeded demo has no empty problem, so two helper files in the git-ignored `.claude/shots/` add and capture one. With the dev servers on 8162 and 5162 (see `.claude/brief.md`), run in this order: reseed with `RESCRIBO_DEMO_PASSWORD='Rescribo-demo-e2e-2026!' uv run python backend/manage.py seed_demo`; `SHOTS_BASE=http://127.0.0.1:5162 node .claude/skills/work-issues/scripts/shots.mjs .claude/shots/after`; `uv run python backend/manage.py shell < .claude/shots/empty-problem.py`; `SHOTS_BASE=http://127.0.0.1:5162 node .claude/shots/empty-problem.mjs .claude/shots/after`. The reseed purges the demo content, so the helper must run after it. Build `.claude/shots/compare.html` with `.claude/skills/work-issues/scripts/compare.py`, using the `empty-problems-*` and `empty-problem-detail-*` shots plus `problems-desktop-light` and `problems-phone-light`. Verify: `empty-problems-*` shows "No reports" beside Open on the "Calendar sync skips recurring events" row only, inside the row at 390px; `empty-problem-detail-*` shows it in the header; `problems-*` matches the before shots. Stop the dev servers afterwards.

## 7. Repository checks

- [x] 7.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 7.2 `task check test build schema-check` passes with PostgreSQL and Redis running. `schema-check` must report no contract change. Record the test counts for the PR.
- [x] 7.3 `RESCRIBO_E2E_API_PORT=8162 RESCRIBO_E2E_FRONTEND_PORT=5162 task e2e` passes. No e2e file changes (D6). Record the counts for the PR.

## Workflow follow-up

- Archive this change in the PR that completes #162 (`/opsx:archive`).
- PR milestone: G. Manual check findings.
