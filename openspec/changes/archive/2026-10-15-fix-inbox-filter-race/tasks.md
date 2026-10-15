# Tasks

Delivers #213. Bug fix; `skip_specs: true`. Change only the files named below. Do not change `frontend/src/test/`, `frontend/e2e/`, or the pure helpers in `inbox-query.ts` and `follow-ups-query.ts`.

Write the inbox test first (group 1) and see it fail, then add the hook (group 2) and move the writers to it (group 3).

## 1. Inbox test in `frontend/src/features/inbox/inbox-page.test.tsx`

- [x] 1.1 Add `act` to the existing `@testing-library/react` import. Add this test at the end of the file. Do not change existing tests.

  ```tsx
  test('keeps two filter changes made before the inbox re-renders', async () => {
    stubApi({
      [reportsPath]: () => page([]),
      [membersPath]: () => json([]),
    })
    renderWorkspaceRoutes(routes, '/inbox?customer=acme')
    const status = await screen.findByRole('group', { name: 'Status' })
    const newChip = await within(status).findByRole('button', { name: /^New/ })
    // One act: both handlers run before the router's transition commits.
    act(() => {
      fireEvent.change(screen.getByRole('combobox', { name: 'Assignee' }), {
        target: { value: 'unassigned' },
      })
      fireEvent.click(newChip)
    })
    expect(screen.getByTestId('location').textContent).toBe(
      '/inbox?customer=acme&assignee=unassigned&triage_state=new',
    )
  })
  ```

- [x] 1.2 Run `cd frontend && npx vitest run src/features/inbox/inbox-page.test.tsx -t "before the inbox re-renders"`. Verify: 1 failed, received `/inbox?customer=acme&triage_state=new`.

## 2. Hook in `frontend/src/hooks/`

- [x] 2.1 Create `frontend/src/hooks/use-live-search-params.ts`:

  ```ts
  import { useCallback, useContext } from 'react'
  import {
    UNSAFE_NavigationContext,
    useSearchParams,
    type Location,
  } from 'react-router-dom'

  type SearchChange = (current: URLSearchParams) => URLSearchParams

  /**
   * useSearchParams whose updates start from the URL as it is now. The router
   * re-renders in a transition after a navigation, so params from the last
   * render can miss a change made a moment earlier.
   */
  export function useLiveSearchParams() {
    const [params, setParams] = useSearchParams()
    const { navigator } = useContext(UNSAFE_NavigationContext)
    const update = useCallback(
      (change: SearchChange) => {
        // Browser and memory history both have it; React Router's type does not.
        const { location } = navigator as { location?: Location }
        if (!location) {
          throw new Error('The router history has no location to read.')
        }
        setParams(change(new URLSearchParams(location.search)))
      },
      [navigator, setParams],
    )
    return [params, update] as const
  }
  ```

- [x] 2.2 Create `frontend/src/hooks/use-live-search-params.test.tsx`:

  ```tsx
  import { act, render, screen } from '@testing-library/react'
  import { BrowserRouter, MemoryRouter } from 'react-router-dom'
  import { afterEach, expect, test } from 'vitest'
  import { LocationProbe } from '@/test/location-probe'
  import { useLiveSearchParams } from './use-live-search-params'

  let update: ReturnType<typeof useLiveSearchParams>[1]

  function Writer() {
    update = useLiveSearchParams()[1]
    return <LocationProbe />
  }

  const set = (key: string, value: string) => (current: URLSearchParams) => {
    const next = new URLSearchParams(current)
    next.set(key, value)
    return next
  }

  function twoQuickUpdates() {
    act(() => {
      update(set('assignee', 'unassigned'))
      update(set('triage_state', 'new'))
    })
    expect(screen.getByTestId('location').textContent).toBe(
      '/inbox?q=csv&assignee=unassigned&triage_state=new',
    )
  }

  afterEach(() => window.history.replaceState(null, '', '/'))

  test('keeps two updates made before a re-render in a memory router', () => {
    render(
      <MemoryRouter initialEntries={['/inbox?q=csv']}>
        <Writer />
      </MemoryRouter>,
    )
    twoQuickUpdates()
  })

  test('keeps two updates made before a re-render in a browser router', () => {
    window.history.replaceState(null, '', '/inbox?q=csv')
    render(
      <BrowserRouter>
        <Writer />
      </BrowserRouter>,
    )
    twoQuickUpdates()
  })
  ```

- [x] 2.3 Run `cd frontend && npx vitest run src/hooks/use-live-search-params.test.tsx`. Verify: 2 passed. Then prove the test: in the hook, temporarily replace `new URLSearchParams(location.search)` with `new URLSearchParams(params)` and add `params` to the `useCallback` dependencies. Rerun and verify 2 failed with `triage_state=new` and no `assignee`. Revert, rerun, verify 2 passed.

## 3. Move the writers to the hook

In each file, import `useLiveSearchParams` from `@/hooks/use-live-search-params`. Remove `useSearchParams` from a `react-router-dom` import only where nothing else in the file uses it. Where a component never reads `params`, destructure as `const [, updateParams] = useLiveSearchParams()`. Paging keeps using the rendered page number, so a double click on Next moves one page.

- [x] 3.1 `frontend/src/features/inbox/report-filter-bar.tsx`: `apply` calls `updateParams((current) => withFilters(current, changes))`. Clear filters calls `updateParams(withoutFilters)`.
- [x] 3.2 `frontend/src/features/inbox/inbox-page.tsx`, `InboxResults`: Clear filters calls `updateParams(withoutFilters)`. Go to the first page calls `updateParams((current) => withPage(current, 1))`. The `useSearchParams` at line 31 only reads and stays.
- [x] 3.3 `frontend/src/features/inbox/report-list.tsx`, the paging component at line 121: Previous and Next call `updateParams((current) => withPage(current, pageNumber - 1))` and `+ 1`. The `useSearchParams` at line 25 only reads and stays.
- [x] 3.4 `frontend/src/features/problems/problems-page.tsx`: in `ProblemsPage`, `onSearch` calls `updateParams((current) => withQuery(current, { q, page: undefined }))`. In `ProblemResults`, Clear search, Go to the first page, and `onPage` pass `(current) => withQuery(current, ...)` with the same query objects as today.
- [x] 3.5 `frontend/src/features/follow-ups/follow-ups-page.tsx`: `BucketTabs` `onChange` calls `updateParams((current) => withBucket(current, next))`. Both paging buttons build `next` from `current` inside `updateParams((current) => { ... return next })` instead of from `params`. `params` stays for `bucketFromParams`, the page read, and `search`.
- [x] 3.6 Verify: `grep -rn "setParams\|setSearchParams" frontend/src` prints nothing. `cd frontend && npx prettier --check src && npm run lint && npm run typecheck` passes.
- [x] 3.7 Rerun 1.2. Verify: 1 passed. Run `cd frontend && npx vitest run src/features/inbox src/features/problems src/features/follow-ups src/hooks`. Verify: no failures, and record the counts.

## 4. Repository checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 4.2 `task check test build schema-check` passes with PostgreSQL and Redis running (ports in `.claude/brief.md`; do not start or stop services). Record the test counts. `schema-check` must report no API change.
- [x] 4.3 `RESCRIBO_E2E_API_PORT=8213 RESCRIBO_E2E_FRONTEND_PORT=5213 task e2e` passes. Record the counts.
- [x] 4.4 Repeat the issue's browser test in three batches, waiting one minute between them: `cd frontend && RESCRIBO_E2E_API_PORT=8213 RESCRIBO_E2E_FRONTEND_PORT=5213 npx playwright test e2e/inbox.spec.ts -g "captures a manual report" --repeat-each=10 --reporter=line`. The whole spec at `--repeat-each=10` signs in 70 times and hits the 10/min login throttle. Record passes, race failures (an `expectSearch` mismatch), and throttle failures (redirect to `/sign-in`) separately. Before the fix, 13 unthrottled local runs had no race failure, so a clean run here is a smoke check, not proof.
- [x] 4.5 No dev server is left on 8213 or 5213.

## Workflow follow-up

- Archive this change in the PR that completes #213 (`/opsx:archive`).
- PR milestone: G. Manual check findings.
- PR "Decisions to review": the hook reads the router history's location through `UNSAFE_NavigationContext` instead of `window.location`; the issue's `setParams((prev) => ...)` was tested and does not fix it; paging keeps the rendered page number; problems and follow-ups get no race test of their own.
- PR Screenshots: "Not applicable: no visible change".
