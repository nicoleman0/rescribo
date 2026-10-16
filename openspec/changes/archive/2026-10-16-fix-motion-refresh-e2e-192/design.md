# Design

## Context

See proposal.md, "Why". Playwright starts three servers. The frontend one is `npm run dev` (Vite 8.3.0, HMR on). With `reuseExistingServer: !process.env.CI`, a local run reuses any server already on the frontend port.

## Evidence

All runs used isolated ports (api 8192, web 5192) and a Vite server started by hand with `DEBUG=vite:hmr,vite:deps` so its log was visible.

| Run | Result |
| --- | --- |
| Full suite, warm dependency cache | 93 passed. No reload in the Vite log. |
| Full suite, `vite --force` (cold cache, as in a new worktree) | Motion passed. 2 unrelated failures: `settings.spec.ts:9`, `ui-foundation.spec.ts:25`. Vite: "the scanner found every used dependency", no reload. |
| The refresh test, `--repeat-each=30` | 20 passed. The other 10 failed at sign-in in `beforeAll` (login throttle, below). |
| The refresh test, 5 batches of `--repeat-each=8`, 65 s apart | 40 passed. |
| Same test with `index.html` touched before `fastForward`, HMR on | 5 of 5 failed at `toEqual(starts)` (rows re-animated after the reload). |
| Same, HMR off | 5 of 5 passed. |

The forced reload gives a different error from the #148 run because it lands before the second `evaluateAll`. "Execution context was destroyed" needs the reload to overlap the `evaluateAll` call. Both are the same fault: the document the test measures is replaced.

### Test-side causes ruled out

- Line 94 is the test's own line, which Playwright prints in its summary. It does not tell which call failed.
- A pending animation would give a `null` start time on the first read. A probe over 8 runs found none.
- No client-side code reloads the page (`grep -rn "location\." frontend/src`).

## Goals / Non-Goals

- Goal: an e2e run started by Playwright cannot have a page reloaded by the dev server.
- Non-goal: e2e against a production build (`vite build` + `vite preview`). It removes the dev client entirely but changes how every spec runs and how long the suite takes.
- Non-goal: the tests in #206 and `seed_test_accounts`.

## Decisions

1. **Turn HMR off for the Playwright-started Vite server.** `vite.config.ts` sets `server.hmr: process.env.RESCRIBO_VITE_HMR !== 'false'`. `playwright.config.ts` adds `RESCRIBO_VITE_HMR: 'false'` to the frontend `webServer` env.
   - Alternative: a guard in `motion.spec.ts` that records main-frame navigations and fails with "the page reloaded during the test". It names the fault but does not remove it, and the trace already shows navigations.
   - Alternative: retry the measurement after a reload. The brief rules out retries.
   - Alternative: `server.ws: false`. It also stops the WebSocket, and the client then logs a connection error on every page. `hmr: false` was enough in the injection run.
2. **Name the variable `RESCRIBO_VITE_HMR`.** A `VITE_` prefix would expose it to client code. The `RESCRIBO_` prefix matches the other variables Playwright passes.

## Risks / Trade-offs

- [A local run reuses a hand-started dev server, which still has HMR] → The brief's isolation commands start the dev server by hand only for screenshots. `task e2e` with the two port variables starts its own server. Say this in the PR.
- [The #148 trigger is not proven] → The fix removes every Vite reload path, not one guessed trigger. If the error recurs with HMR off, the trace will show a navigation that does not come from Vite.
- [Runtime dependency discovery with HMR off cannot reload the page to pick up new chunks] → The scanner finds every dependency today (cold-cache run). A new dependency the scanner misses would surface as a failed module load in e2e, not a silent pass.

## Measuring repeats

`--repeat-each=N` reruns `beforeAll`, so every repeat signs the demo user in again. The login throttle is 10 per minute per identity (`backend/config/settings.py`, `login_identity`). Repeat in batches of at most 8, about a minute apart.
