# Design

## Context

The app uses `BrowserRouter` (`frontend/src/main.tsx`). Component tests use `MemoryRouter` through `renderWorkspaceRoutes` (`frontend/src/test/render.tsx`, shared, not owned by this change).

In React Router 7.18.4 both routers push the history entry synchronously, then apply the new location with `React.startTransition`. `useSearchParams` returns `searchParams` memoised from the rendered location, and its setter passes that same object to a function argument (`nextInit(new URLSearchParams(searchParams))` in `react-router/dist/development/chunk-HQO5H5CC.js`). Until the transition commits, every handler on the page sees the old params.

A throwaway test made two updates inside one `act` and checked the URL:

| Base for the second update | `MemoryRouter` | `BrowserRouter` |
| --- | --- | --- |
| Render-time `params` (current code) | first lost | first lost |
| `setParams((prev) => ...)` (the issue's suggestion) | first lost | first lost |
| `window.location.search` | first lost | kept |
| The router history's `location.search` | kept | kept |

The same test on `InboxPage` (Assignee, then the New chip) gave `/inbox?customer=acme&triage_state=new`, the issue's symptom.

## Goals / Non-Goals

**Goals:**
- Every URL change the issue lists starts from the URL as it is now.
- The rule lives in one hook.
- A test fails if a writer goes back to render-time params.

**Non-Goals:**
- Other flaky tests (#206, #192) and #208.
- Writers the issue does not list. All other `useSearchParams` calls in `frontend/src` only read.
- Changing `frontend/e2e/inbox.spec.ts`.

## Decisions

**Read the router history's location, not `window.location`.** The hook reads `navigator.location.search` from `UNSAFE_NavigationContext`. Both browser and memory history expose `location`, and both update it synchronously on push. `window.location` works only under `BrowserRouter`, so every existing component test that changes a filter from a non-empty URL would lose its params (for example the follow-ups paging test expects `bucket=needs_approval&page=2`). Moving the shared test helper to `BrowserRouter` is the alternative; it touches a shared file and every test that uses it. See question 1 in the plan summary.

**The setter takes only a function of the current params.** `useLiveSearchParams()` returns `[params, update]`. `params` is the render-time value for reading. `update(change)` calls `change(current)` and passes the result to the router's `setSearchParams`. There is no overload that takes a ready-made `URLSearchParams`, so a caller cannot pass one built from stale params. The existing pure helpers (`withFilters`, `withoutFilters`, `withPage`, `withQuery`, `withBucket`) stay as they are and become the `change` functions.

**Fail loudly if the history has no location.** `Navigator` in React Router's types has no `location`. The hook narrows it and throws a clear error if it is missing, so a router upgrade that drops it fails in every unit test instead of silently losing filters.

**Test the rule once, and the inbox wiring once.** The hook test covers both router types. One inbox test reproduces the issue's path. Problems and follow-ups get no race test of their own: their existing tests already click through the changed handlers, and the rule they rely on is the hook's.

## Risks / Trade-offs

- [`UNSAFE_NavigationContext` and `history.location` are not public API] → Confined to one file; the hook throws and its test fails if either changes.
- [Local e2e repeats rarely show the race] → 13 local runs of the inbox test on the current code had no race failure. The unit test is the proof; the e2e repeat is a smoke check.
- [The sign-in throttle (`login_identity`, 10/min in `backend/config/settings.py`) fails repeated e2e runs at `/sign-in`] → Keep a single repeat batch to 10 runs, or wait a minute between batches, and report throttle failures separately.
