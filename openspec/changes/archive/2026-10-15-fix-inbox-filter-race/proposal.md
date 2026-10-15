# Proposal

Delivers GitHub issue #213 (milestone G. Manual check findings).

## Why

A member sets Assignee to Unassigned and then clicks the New chip. The inbox shows `?triage_state=new` and the assignee filter is gone. CI hit the same race three times in six e2e runs on 2026-10-12 (`frontend/e2e/inbox.spec.ts:60`).

Each `useSearchParams` writer builds the next URL from the `params` of its last render. The router pushes the URL at once but re-renders in a transition. A second change in that gap starts from the old URL and drops the first. `web-interface` "Inbox status chips" requires a chip to apply on top of the other active filters, so the code diverges from it.

The issue suggests `setParams((prev) => ...)`. That does not fix it: React Router 7.18.4 passes the function the same render-time params. A throwaway test confirmed this under both `MemoryRouter` and `BrowserRouter`.

## What Changes

- A new hook, `useLiveSearchParams`, builds each URL change from the router's current location instead of the last render.
- Every writer the issue lists uses it: the inbox filter bar and both Clear filters buttons, inbox paging and its first-page button, the problems search, clear-search, first-page, and paging, and the follow-ups bucket tabs and paging.
- A hook test and an inbox component test make two changes before a re-render and assert both survive. The component test fails on the current code.

No backend, API, `frontend/openapi.yaml`, or spec change. Nothing rendered changes. The change sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The code is brought back in line with `web-interface`.

## Impact

- New: `frontend/src/hooks/use-live-search-params.ts` and its test.
- `frontend/src/features/inbox/report-filter-bar.tsx`, `inbox-page.tsx`, `report-list.tsx`, `inbox-page.test.tsx`.
- `frontend/src/features/problems/problems-page.tsx`.
- `frontend/src/features/follow-ups/follow-ups-page.tsx`.
