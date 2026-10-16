# Proposal

Delivers GitHub issue #192 (milestone G. Manual check findings).

## Why

"background refresh animates only the new row with capped stagger" (`frontend/e2e/motion.spec.ts:94`) failed once on the #148 branch with "Execution context was destroyed, most likely because of a navigation", and passed on rerun. That error means the page document was replaced while an `evaluateAll` ran.

Nothing in the test or the app replaces the document after `openInbox`:

- The app has no `location.reload`, `location.assign`, or `location.href` write outside the GitHub connect button. React Router navigations stay in the same document.
- `openDemoInbox` already waits for the load event and the `/inbox` URL.
- `page.clock.install()` leaves time running. `fastForward(30_000)` fires the React Query refetch timers and Vite's 30 s ping, and none of them navigate.

The one thing that reloads the document is the Vite dev client. It reloads when a watched file changes, when dependencies are re-optimized, or after the dev server connection drops. Playwright starts e2e against `vite` with HMR on. A forced reload in the middle of this test fails it every time (see design.md). The trigger in the #148 run is unknown: that worktree, its trace, and its Vite log are gone.

## What Changes

- The Vite server that Playwright starts runs with HMR off, so a file save or dependency re-optimization cannot reload a page mid-test.
- `vite.config.ts` reads one environment variable for this. Dev servers started by hand keep HMR.
- `motion.spec.ts` is unchanged. No race inside the test was found (design.md, "Test-side causes ruled out").

No app behaviour, API, or spec change. The change sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `frontend/vite.config.ts`: `server.hmr` follows `RESCRIBO_VITE_HMR`.
- `frontend/playwright.config.ts`: the frontend `webServer` sets `RESCRIBO_VITE_HMR=false`.
- Every e2e spec gains the same protection when Playwright starts the server. A reused, hand-started dev server still has HMR.
