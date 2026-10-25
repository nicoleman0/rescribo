# Tasks

Delivers #221. Tooling only; `skip_specs: true`. Touch only `frontend/e2e/ui-foundation.spec.ts`, `frontend/e2e/settings.spec.ts`, and `frontend/e2e/follow-ups.spec.ts` (approved in `.switchyard/answers/plan.md`). No raised timeouts, no `test.slow()`, no retries, no app code.

## 1. Exact heading in the desktop shell test

- [x] 1.1 In `ui-foundation.spec.ts` "shell at desktop width", add `exact: true` to `getByRole('heading', { name: 'Follow-ups' })`. Change nothing else in that file. Verify: `git diff frontend/e2e/ui-foundation.spec.ts` shows one changed locator.
- [x] 1.2 Prove the fix against the empty state. Run "shell at desktop width" once with a temporary `page.route('**/api/workspaces/*/follow-ups/**', ...)` that answers `{ count: 0, next: null, previous: null, results: [] }`, first on the old locator, then on the new one. Verify: the old locator fails with a strict mode violation naming both headings; the new one passes. Remove the temporary route; do not commit it. Record both results for the PR.
- [x] 1.3 In `follow-ups.spec.ts` (the `?bucket=needs_approval` assertion, line 283), add `exact: true` to `getByRole('heading', { level: 1, name: 'Follow-ups' })`. Change nothing else in that file. Prove it the same way as 1.2 if an empty `needs_approval` bucket is cheap to mock with `page.route`; otherwise say why not in the PR.

## 2. Split the settings journey

Move assertions as they are. Do not reword, reorder, or drop one, apart from the explicit sign-in steps that `beforeAll` replaces.

- [x] 2.1 Wrap the journey in `test.describe('Settings owner journey', ...)` with `test.describe.configure({ mode: 'serial' })`, `test.use({ storageState: seedSessionPath('settings-owner') })`, and a `beforeAll` that calls `saveSeedSession(browser, info.project.use.baseURL, seedSessionPath('settings-owner'), 9)`. Keep the block above the four other tests in the file.
- [x] 2.2 Test "owner keeps one active owner and invites a member who sees only member settings": current lines 24 to 61, starting at `page.goto('/settings/members')`.
- [x] 2.3 Tests "settings sections fit, meet touch targets and pass axe at <width>px": one `for (const width of [390, 320])` loop that creates one test per width. Each starts with `page.goto('/settings/members')` and the viewport size, then runs the current inner loop over the five sections (lines 64 to 85).
- [x] 2.4 Test "members page lists the new member on desktop and mobile, and the owner promotes them": current lines 87 to 108.
- [x] 2.5 Test "owner deletes a report, then the workspace, after typed confirmation": current lines 109 to 141.
- [x] 2.6 Verify: `RESCRIBO_E2E_API_PORT=8221 RESCRIBO_E2E_FRONTEND_PORT=5221 npx playwright test settings.spec.ts --reporter=list` from `frontend` passes 3 times in a row, each run separate (the journey deletes its workspace, so `--repeat-each` cannot work). Record each new test's duration and the load average (`uptime`) for the PR. On an unloaded machine no test in the block should exceed 10s; if one does, report it instead of tuning.
- [x] 2.7 Verify the serial dependency: with a temporary failing assertion in test 2.2, the later tests in the block report as skipped, not failed. Remove the temporary assertion.

## 3. Repository checks

- [x] 3.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 3.2 `task check test build schema-check` passes with PostgreSQL and Redis running (ports in `.switchyard/brief.md`; do not start or stop services). Record the counts for the PR.
- [x] 3.3 Clear `frontend/node_modules/.vite` in this worktree, then `RESCRIBO_E2E_API_PORT=8221 RESCRIBO_E2E_FRONTEND_PORT=5221 task e2e` passes. Record the counts and the settings block durations for the PR.
- [x] 3.4 `git status --short` lists only the two spec files and `openspec/changes/`. No dev server is left on 8221 or 5221.

## Workflow follow-up

- Archive this change in the PR that completes #221 (`/opsx:archive`).
- PR milestone: G. Manual check findings.
- PR "Decisions to review": serial split instead of a raised timeout; the cause evidence from `design.md`, stated plainly as machine load and the 30s test timeout, not the cold Vite cache, with no error output from the #221 run to confirm it; the same-pattern list, noticed and not changed; the second `h1` from `EmptyState` (coordinator opens a separate issue).
- PR Screenshots: "Not applicable: tooling only."
