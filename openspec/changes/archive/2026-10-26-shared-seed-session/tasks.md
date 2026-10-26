# Tasks

## 1. Shared core

- [x] 1.1 Add `frontend/e2e/session.ts` with `authDir`, `signIn(page, credentials)`, and `saveSession(browser, baseURL, sessionPath, credentials)` as in design.md; verify `npm run typecheck` from `frontend` passes.
- [x] 1.2 Rebuild `seed-session.ts` on the core and export `readSeed()`; keep `seedSessionPath` and `saveSeedSession` signatures and return value. Verify `z-product-states`, `command-palette`, `theme-tokens`, `settings`, and `ui-foundation` pass when run alone.
- [x] 1.3 Rebuild `demo-session.ts` on the core; keep `signInAsDemo`, `demoSessionPath`, `saveDemoSession`, and `openDemoInbox` signatures. Verify `demo`, `motion`, and `themes` pass when run alone.

## 2. Move the two specs

- [x] 2.1 `report-triage.spec.ts`: call `saveSeedSession(browser, baseURL, seedSessionPath('triage-owner'), 4)` in `beforeAll`; delete the local `saveSession`, `authDir`, `seedPath`, `Seed`, and unused imports. Verify `git diff` shows no test or assertion removed or reordered, and the spec passes alone.
- [x] 2.2 `follow-ups.spec.ts`: call `saveSeedSession(browser, baseURL, seedSessionPath('follow-ups-owner'), 5)` in `beforeAll`; move `ensureFollowUpOwner` and the user 7 member sign-in to `readSeed()` and `signIn`; delete the local `saveSession`, `authDir`, `seedPath`, `Seed`, and unused imports. Verify `git diff` shows no test or assertion removed or reordered, and the spec passes alone.
- [x] 2.3 Verify `grep -n "storageState({ path\|seed.json\|'.auth'" frontend/e2e/*.spec.ts` finds no session-saving or seed-path code left in the two specs.

## 3. Repository checks

- [x] 3.1 Run `task check test build schema-check` with PostgreSQL and Redis running; all pass.
- [x] 3.2 Run `RESCRIBO_E2E_API_PORT=8182 RESCRIBO_E2E_FRONTEND_PORT=5182 task e2e`; all pass. Record the pass count.
- [x] 3.3 Run `npx @fission-ai/openspec validate --all --strict`; it passes.

## Workflow follow-up

- Archive the change in the PR that completes it.
