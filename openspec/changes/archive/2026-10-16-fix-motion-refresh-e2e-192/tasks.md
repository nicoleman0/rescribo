# Tasks

Delivers #192. Tooling only; `skip_specs: true`. Change only `frontend/vite.config.ts` and `frontend/playwright.config.ts`. Do not change app code, `motion.spec.ts`, or other e2e files. Ports: api 8192, web 5192 (see `.claude/brief.md`).

## 1. Show the failure first

- [x] 1.1 Temporarily add, after `await page.route(...)` and before `page.clock.fastForward(30_000)` in the refresh test, `utimesSync('index.html', new Date(), new Date())` (import from `node:fs`) and `await new Promise((r) => setTimeout(r, 500))`. Do not commit it.
- [x] 1.2 From `frontend`, run `RESCRIBO_E2E_API_PORT=8192 RESCRIBO_E2E_FRONTEND_PORT=5192 npx playwright test e2e/motion.spec.ts -g "background refresh" --repeat-each=5`. Verify 5 of 5 fail at `toEqual(starts)`. Make sure nothing else listens on 5192 first, so Playwright starts its own server.

## 2. Turn HMR off for Playwright's Vite server

- [x] 2.1 `frontend/vite.config.ts`: in `server`, add `hmr: process.env.RESCRIBO_VITE_HMR !== 'false',` with a one-line comment saying why: Playwright turns it off so a file save cannot reload a page mid-test.
- [x] 2.2 `frontend/playwright.config.ts`: in the frontend `webServer` entry, add `RESCRIBO_VITE_HMR: 'false'` to `env`, next to `API_PROXY_TARGET`.
- [x] 2.3 Rerun 1.2 with the temporary edit still in place. Verify 5 of 5 pass. Then remove the temporary edit and verify `git diff frontend/e2e` is empty.

## 3. Show the fix holds

- [x] 3.1 Run the refresh test 40 times in 5 batches of `--repeat-each=8`, about 65 s apart (the login throttle allows 10 sign-ins a minute; `--repeat-each=20` fails at sign-in). Verify 40 of 40 pass. Record the numbers for the PR. All five batches passed 8/8 (40/40).
- [x] 3.2 Verify the Vite setting through its config loader from `frontend`: `node -e "import('vite').then(v=>v.resolveConfig({},'serve')).then(c=>console.log(c.server.hmr))"` outputs an enabled HMR configuration object; `RESCRIBO_VITE_HMR=false node -e "import('vite').then(v=>v.resolveConfig({},'serve')).then(c=>console.log(c.server.hmr))"` outputs `false`. The live HMR edit check was not run, per `.claude/answers/impl-2.md`.

## 4. Repository checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 4.2 `task check test build schema-check` passes with PostgreSQL and Redis running. Record the counts: backend 1,132; frontend 330; Rust 26; production build and schema checks passed.
- [x] 4.3 `RESCRIBO_E2E_API_PORT=8192 RESCRIBO_E2E_FRONTEND_PORT=5192 task e2e` passes. Record the counts. If `settings.spec.ts` or `ui-foundation.spec.ts` fails, check it against #206 and report it; do not fix it here. The full suite passed 93/93, including settings and UI foundation.
- [x] 4.4 No server is left on 8192 or 5192. `task worker-check` is not needed: no worker wiring changes.

## Workflow follow-up

- Archive this change in the PR that completes #192 (`/opsx:archive`).
- PR milestone: G. Manual check findings.
- PR "Decisions to review": HMR off for the Playwright-started server only; the #148 trigger is not proven, the fix removes every Vite reload path; a reused hand-started server keeps HMR.
- PR Screenshots: "Not applicable: tooling only".
